"""Tests for packaging metadata that is maintained by hand."""

import importlib
import re
import subprocess
import tarfile
import tempfile
import zipfile
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


def test_runtime_dependencies_match_between_pyproject_and_setup_py() -> None:
    """setup.py and pyproject.toml must declare the same runtime dependencies."""
    import tomllib

    pyproject_deps = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))[
        "project"
    ]["dependencies"]
    setup_text = (ROOT / "setup.py").read_text("utf-8")
    for dep in pyproject_deps:
        assert f'"{dep}"' in setup_text


def test_push_dispatch_allowlist_is_packaged() -> None:
    module = importlib.import_module("pyimouapi.push_dispatch_allowlist")
    assert "iotproperty" in module.PUSH_DISPATCH_MSG_TYPES_LOWER


def test_push_dispatch_allowlist_in_wheel_and_sdist() -> None:
    """Built artifacts must ship the allowlist module, not only the source tree."""
    module_suffix = "pyimouapi/push_dispatch_allowlist.py"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        subprocess.run(
            ["uv", "build", "-o", str(out)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        wheels = list(out.glob("*.whl"))
        assert wheels, "expected a wheel"
        with zipfile.ZipFile(wheels[0]) as archive:
            assert any(name.endswith(module_suffix) for name in archive.namelist())
        sdists = list(out.glob("*.tar.gz"))
        assert sdists, "expected an sdist"
        with tarfile.open(sdists[0], "r:gz") as archive:
            assert any(
                member.name.endswith(module_suffix) for member in archive.getmembers()
            )


def test_py_typed_marker_is_present() -> None:
    """Without the marker, PEP 561 tells consumers to ignore our annotations."""
    assert (ROOT / "pyimouapi" / "py.typed").is_file()


def test_py_typed_is_declared_as_package_data() -> None:
    """The marker only helps consumers if it is shipped in the distribution."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    setup_py = (ROOT / "setup.py").read_text(encoding="utf-8")

    assert 'pyimouapi = ["py.typed", "data/*.yaml"]' in pyproject
    assert '"pyimouapi": ["py.typed", "data/*.yaml"]' in setup_py
