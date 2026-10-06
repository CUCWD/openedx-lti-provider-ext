"""Ensure the CI lint baseline rejects new findings and tool failures."""

import json
from collections import Counter
from subprocess import CompletedProcess

import pytest

from test_utils import check_quality


@pytest.mark.parametrize("count, expected", [(1, 0), (2, 1)])
def test_baseline_rejects_increased_findings(monkeypatch, tmp_path, count, expected):
    """Existing findings pass; additional occurrences fail."""
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"known finding": 1}), encoding="utf-8")
    monkeypatch.setattr(check_quality, "BASELINE", baseline)
    monkeypatch.setattr(check_quality.sys, "argv", ["check_quality.py"])
    monkeypatch.setattr(check_quality, "collect_findings", lambda: Counter({"known finding": count}))
    assert check_quality.main() == expected


def test_baseline_rejects_new_diagnostic(monkeypatch, tmp_path):
    """A new diagnostic cannot pass using an unrelated baseline entry."""
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"old finding": 1}), encoding="utf-8")
    monkeypatch.setattr(check_quality, "BASELINE", baseline)
    monkeypatch.setattr(check_quality.sys, "argv", ["check_quality.py"])
    monkeypatch.setattr(check_quality, "collect_findings", lambda: Counter({"new finding": 1}))
    assert check_quality.main() == 1


def test_tool_crashes_fail(monkeypatch):
    """A tool traceback is an error even with a normally permitted exit code."""
    result = CompletedProcess([], 1, "", "Traceback (most recent call last)")
    monkeypatch.setattr(check_quality.subprocess, "run", lambda *args, **kwargs: result)
    with pytest.raises(RuntimeError, match="Tool failed"):
        check_quality.run_tool(["tool"], {0, 1})
