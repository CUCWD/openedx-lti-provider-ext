"""Load unchanged outcome helpers from the pinned platform checkout."""

import importlib.util
import os
import sys
from pathlib import Path

platform_root = os.environ.get("LTI_TEST_PLATFORM_ROOT")
if not platform_root:
    raise RuntimeError("Set LTI_TEST_PLATFORM_ROOT to an Open edX platform checkout to run outcome tests.")
source = Path(platform_root) / "lms/djangoapps/lti_provider/outcomes.py"
spec = importlib.util.spec_from_file_location(__name__, source)
module = importlib.util.module_from_spec(spec)
sys.modules[__name__] = module
spec.loader.exec_module(module)
