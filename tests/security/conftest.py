"""
Conftest for mock-based adversarial security tests.

Automatically applies the 'security' marker to every test collected from this
directory so CI profiles can run or exclude the entire category without
requiring per-file pytestmark declarations.
"""

import pytest


def pytest_collection_modifyitems(config, items: list) -> None:
    for item in items:
        if item.fspath.dirpath().basename == "security":
            item.add_marker(pytest.mark.security)
