"""Changelog/version parity — A32-changelog-version-parity.

`2.1.0` was tagged and released with no `CHANGELOG.md` entry, and the file
separately carried two sibling `## [2.0.0]` headings for the single tagged
`v2.0.0` release. This locks both classes of defect: the current version must
have a matching heading, and no heading may be duplicated.
"""

import re
from pathlib import Path

from imgtools_m8 import __version__

REPO_ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

_HEADING_RE = re.compile(r"^## \[(?P<version>\d+\.\d+\.\d+)\]", re.MULTILINE)


def test_changelog_exists() -> None:
    assert CHANGELOG.exists(), "CHANGELOG.md must exist at the repo root."


def test_current_version_has_a_changelog_entry() -> None:
    """The version in `imgtools_m8.__version__` must head a CHANGELOG entry."""
    headings = _HEADING_RE.findall(CHANGELOG.read_text(encoding="utf-8"))
    assert __version__ in headings, (
        f"CHANGELOG.md has no '## [{__version__}]' heading for the current "
        f"version (imgtools_m8.__version__ = {__version__!r}); every "
        "published version must be documented."
    )


def test_changelog_headings_are_unique() -> None:
    """No two entries may claim the same version (this repo's original A32 finding)."""
    headings = _HEADING_RE.findall(CHANGELOG.read_text(encoding="utf-8"))
    duplicates = {v for v in headings if headings.count(v) > 1}
    assert not duplicates, (
        f"CHANGELOG.md has duplicate '## [x.y.z]' headings for: {sorted(duplicates)}"
    )
