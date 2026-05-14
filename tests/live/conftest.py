"""
Conftest for live red-team tests.

All tests here carry the 'live' marker.  This hook auto-skips them when the
target compose stack is not reachable, so a plain `pytest` run (which already
ignores tests/live via addopts) and an explicit `pytest tests/live` run on a
machine without the stack both produce clean, informative output.
"""

import pytest
import requests


def pytest_collection_modifyitems(config, items: list) -> None:
    stack_up = False
    try:
        r = requests.get("http://localhost:9000/user/health/", timeout=2)
        r.raise_for_status()
        stack_up = True
    except Exception:
        pass

    if not stack_up:
        skip = pytest.mark.skip(
            reason="Live stack not reachable — start RS256_m8 compose first"
        )
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip)
