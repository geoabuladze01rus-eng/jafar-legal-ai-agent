from __future__ import annotations

import tomllib
from pathlib import Path


def test_editable_install_uses_explicit_setuptools_src_discovery() -> None:
    config = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())

    assert config["build-system"]["build-backend"] == "setuptools.build_meta"
    assert config["tool"]["setuptools"]["package-dir"] == {"": "src"}
    assert config["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]
    assert config["tool"]["setuptools"]["packages"]["find"]["include"] == ["jafar*"]
