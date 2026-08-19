"""Tests for packaging metadata that is maintained by hand."""

import re
from pathlib import Path

import pyimouapi

ROOT = Path(__file__).parent.parent


def declared_version(path: Path, pattern: str) -> str:
    """Return the version string declared in the given file."""
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    assert match is not None, f"no version found in {path.name}"
    return match.group(1)


def test_version_is_declared_consistently() -> None:
    """Releases update three files by hand; a mismatch ships the wrong version."""
    pyproject = declared_version(ROOT / "pyproject.toml", r'^version = "([^"]+)"')
    setup_py = declared_version(ROOT / "setup.py", r'version="([^"]+)"')

    assert pyimouapi.__version__ == pyproject == setup_py


def test_py_typed_marker_is_present() -> None:
    """Without the marker, PEP 561 tells consumers to ignore our annotations."""
    assert (ROOT / "pyimouapi" / "py.typed").is_file()


def test_py_typed_is_declared_as_package_data() -> None:
    """The marker only helps consumers if it is shipped in the distribution."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    setup_py = (ROOT / "setup.py").read_text(encoding="utf-8")

    assert 'pyimouapi = ["py.typed"]' in pyproject
    assert '"pyimouapi": ["py.typed"]' in setup_py
