"""Shared helpers: fixture discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES = Path(__file__).parent.parent / "examples"


def fixture_names(*, prefix: str | None = None, exclude: tuple[str, ...] = ()) -> list[str]:
    names = []
    for directory in sorted(FIXTURES.iterdir()):
        if not directory.is_dir() or directory.name.startswith(exclude):
            continue
        if prefix is None or directory.name.startswith(prefix):
            names.append(directory.name)
    return names


def read(name: str, filename: str) -> str:
    return (FIXTURES / name / filename).read_text(encoding="utf-8")


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
