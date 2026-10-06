"""Run all quality tools, rejecting findings beyond the reviewed legacy baseline."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / ".quality-baseline.json"
TARGETS = ["openedx_lti_provider_ext", "tests", "test_utils", "manage.py", "setup.py"]


def run_tool(arguments, allowed_codes):
    """Capture diagnostics, failing closed on crashes or unexpected exit codes."""
    result = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode not in allowed_codes or "Traceback (most recent call last)" in result.stderr:
        raise RuntimeError(f"Tool failed: {arguments}\n{result.stdout}\n{result.stderr}")
    return result


def collect_findings():
    """Normalize locations while retaining diagnostic identity and occurrence counts."""
    findings = Counter()
    result = run_tool(
        ["pylint", "--output-format=json", "--reports=n", "--score=n", *TARGETS],
        set(range(32)),
    )
    for item in json.loads(result.stdout):
        if item["type"] == "fatal":
            raise RuntimeError(f"Pylint fatal error: {item}")
        path = Path(item["path"])
        if path.is_absolute():
            path = path.relative_to(ROOT)
        findings[f"pylint | {path} | {item['message-id']} | {item['message']}"] += 1

    result = run_tool(
        ["pycodestyle", "--format=%(path)s|%(code)s|%(text)s", *TARGETS], {0, 1},
    )
    for line in result.stdout.splitlines():
        findings[f"pycodestyle | {line}"] += 1

    result = run_tool(["pydocstyle", *TARGETS], {0, 1})
    before = sum(findings.values())
    location = None
    for line in (result.stdout + result.stderr).splitlines():
        match = re.match(r"(.+\.py):\d+ (.*)", line)
        if match:
            location = match.group(1)
        elif re.match(r"\s+D\d+: ", line) and location:
            findings[f"pydocstyle | {location} | {line.strip()}"] += 1
        elif line.strip():
            raise RuntimeError(f"Unrecognized pydocstyle output: {line}")

    if result.returncode and sum(findings.values()) == before:
        raise RuntimeError("pydocstyle failed without recognized diagnostics")

    # A file with legacy import ordering is allowed only while its contents are
    # unchanged. Any edit requires formatting it or explicitly reviewing a new baseline.
    result = run_tool(["isort", "--check-only", "--diff", *TARGETS, "test_settings.py"], {0, 1})
    before = sum(findings.values())
    for line in result.stderr.splitlines():
        match = re.match(r"ERROR: (.+) Imports are incorrectly sorted and/or formatted\.", line)
        if match:
            path = Path(match.group(1)).resolve()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            findings[f"isort | {path.relative_to(ROOT)} | sha256:{digest}"] += 1
        elif line.strip():
            raise RuntimeError(f"Unrecognized isort output: {line}")
    if result.returncode and sum(findings.values()) == before:
        raise RuntimeError("isort failed without recognized diagnostics")
    return findings


def main():
    """Compare current findings to the baseline; updates require an explicit flag."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()
    current = collect_findings()
    if args.update_baseline:
        BASELINE.write_text(json.dumps(dict(sorted(current.items())), indent=2) + "\n", encoding="utf-8")
        print(f"Recorded {sum(current.values())} findings; review the baseline diff before committing.")
        return 0
    baseline = Counter(json.loads(BASELINE.read_text(encoding="utf-8")))
    added = current - baseline
    if added:
        for finding, count in sorted(added.items()):
            print(f"NEW ({count}): {finding}")
        return 1
    print(f"Quality passed: {sum(current.values())} known findings; no new findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
