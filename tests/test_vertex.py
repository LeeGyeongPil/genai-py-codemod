"""AC-3: Vertex AI SDK (vertexai.generative_models) conversion."""

from __future__ import annotations

import pytest
from conftest import fixture_names, read

from genai_py_codemod import migrate_source

NAMES = fixture_names(prefix="vertex_")


@pytest.mark.parametrize("name", NAMES)
def test_vertex_golden(name: str) -> None:
    result = migrate_source(read(name, "before.py"), path=f"{name}/before.py")
    assert result.code == read(name, "expected.py")
    assert not migrate_source(result.code).changed  # idempotent


def test_init_becomes_vertex_client() -> None:
    out = migrate_source(read("vertex_basic", "before.py")).code
    assert 'client = genai.Client(vertexai=True, project="demo-project", location="us-central1")' in out
    assert "vertexai.init" not in out
    assert "import vertexai" not in out


def test_generation_config_class_becomes_generate_content_config() -> None:
    out = migrate_source(read("vertex_basic", "before.py")).code
    assert "types.GenerateContentConfig(" in out
    assert "GenerationConfig(" not in out.replace("GenerateContentConfig(", "")
    assert 'model = "gemini-2.5-flash"' in out


def test_safety_setting_class_is_renamed() -> None:
    out = migrate_source(read("vertex_safety", "before.py")).code
    assert "types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT" in out


def test_mixing_both_sdks_is_reported() -> None:
    source = (
        "import google.generativeai as genai\nimport vertexai\n"
        "from vertexai.generative_models import GenerativeModel\n"
        'genai.configure(api_key="k")\nvertexai.init(project="p", location="l")\n'
        'a = genai.GenerativeModel("x")\nb = GenerativeModel("y")\n'
        'print(a.generate_content("1"), b.generate_content("2"))\n'
    )
    result = migrate_source(source)
    assert not result.changed
    assert "mixed-sdk" in {f.code for f in result.findings}
