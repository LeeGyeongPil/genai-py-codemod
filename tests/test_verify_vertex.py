"""AC-7: cross-interpreter check for the Vertex AI SDK (old SDK in its own environment).

google-cloud-aiplatform pins google-genai<3, so the old Vertex SDK needs a separate interpreter. Create it with
``uv run python scripts/make_vertex_env.py`` and set GENAI_PY_CODEMOD_VERTEX_PYTHON. Without it these tests are skipped.
"""

from __future__ import annotations

import os

import pytest
from conftest import FIXTURES, fixture_names

from genai_py_codemod import verify_files

VERTEX_PYTHON = os.environ.get("GENAI_PY_CODEMOD_VERTEX_PYTHON")
pytestmark = pytest.mark.skipif(not VERTEX_PYTHON, reason="GENAI_PY_CODEMOD_VERTEX_PYTHON is not set")


@pytest.mark.parametrize("name", fixture_names(prefix="vertex_"))
def test_vertex_requests_are_equivalent(name: str) -> None:
    """Old Vertex SDK in the aiplatform environment vs. google-genai 3.x in the normal environment."""
    folder = FIXTURES / name
    result = verify_files(folder / "before.py", folder / "expected.py", old_python=VERTEX_PYTHON)
    assert result.equivalent, [d.render() for d in result.diffs]
    assert result.network_attempts == 0
    assert result.warnings == ["API version v1 -> v1beta1"]  # a warning only, never a failure


@pytest.mark.parametrize("name", fixture_names(prefix="vertex_"))
def test_vertex_requests_are_equivalent_with_genai_2x(name: str) -> None:
    """The migrated file also works against google-genai 2.x (httpx instead of httpx2)."""
    folder = FIXTURES / name
    result = verify_files(
        folder / "before.py", folder / "expected.py", old_python=VERTEX_PYTHON, new_python=VERTEX_PYTHON
    )
    assert result.equivalent, [d.render() for d in result.diffs]
    assert result.sdk_versions["google-genai"].startswith("2.")
