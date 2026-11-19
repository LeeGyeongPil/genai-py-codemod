"""Qualified names of the old SDKs and what they map to in google-genai."""

from __future__ import annotations

DEV_PREFIX = "google.generativeai"
VERTEX_PREFIX = "vertexai"

GENERATIVE_MODEL = frozenset(
    {
        "google.generativeai.GenerativeModel",
        "google.generativeai.generative_models.GenerativeModel",
        "vertexai.generative_models.GenerativeModel",
        "vertexai.generative_models._generative_models.GenerativeModel",
    }
)
CONFIGURE = frozenset({"google.generativeai.configure"})
VERTEX_INIT = frozenset({"vertexai.init"})
EMBED_CONTENT = frozenset({"google.generativeai.embed_content"})

GENERATION_CONFIG = frozenset(
    {
        "google.generativeai.GenerationConfig",
        "google.generativeai.types.GenerationConfig",
        "google.generativeai.types.generation_types.GenerationConfig",
        "vertexai.generative_models.GenerationConfig",
    }
)

# Old name -> attribute on google.genai.types that replaces it.
RENAMED_TYPES: dict[str, str] = {
    "google.generativeai.types.HarmCategory": "HarmCategory",
    "google.generativeai.types.HarmBlockThreshold": "HarmBlockThreshold",
    "google.generativeai.types.safety_types.HarmCategory": "HarmCategory",
    "google.generativeai.types.safety_types.HarmBlockThreshold": "HarmBlockThreshold",
    "vertexai.generative_models.HarmCategory": "HarmCategory",
    "vertexai.generative_models.HarmBlockThreshold": "HarmBlockThreshold",
    "vertexai.generative_models.SafetySetting": "SafetySetting",
}
for _name in GENERATION_CONFIG:
    RENAMED_TYPES[_name] = "GenerateContentConfig"

# Calls the transformer rewrites (any other use of these names, e.g. a type annotation, is reported).
CONVERTED_CALLS = GENERATIVE_MODEL | CONFIGURE | VERTEX_INIT | EMBED_CONTENT
# Module paths that are only prefixes of handled names (``genai.types.HarmCategory``).
HANDLED_PREFIXES = frozenset(
    {
        "google",
        "google.generativeai",
        "google.generativeai.types",
        "google.generativeai.types.safety_types",
        "google.generativeai.types.generation_types",
        "google.generativeai.generative_models",
        "vertexai",
        "vertexai.generative_models",
        "vertexai.generative_models._generative_models",
    }
)

MODEL_METHODS = frozenset({"generate_content", "generate_content_async", "start_chat", "count_tokens"})
CHAT_METHODS = frozenset({"send_message"})
CONFIG_KEYWORDS = ("generation_config", "safety_settings", "system_instruction", "tools", "tool_config")
CALL_CONFIG_KEYWORDS = ("generation_config", "safety_settings", "tools", "tool_config")

SAFETY_CATEGORY_NAMES = {
    "harassment": "HARM_CATEGORY_HARASSMENT",
    "hate": "HARM_CATEGORY_HATE_SPEECH",
    "hate_speech": "HARM_CATEGORY_HATE_SPEECH",
    "sex": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "sexual": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "sexually_explicit": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "danger": "HARM_CATEGORY_DANGEROUS_CONTENT",
    "dangerous": "HARM_CATEGORY_DANGEROUS_CONTENT",
    "dangerous_content": "HARM_CATEGORY_DANGEROUS_CONTENT",
}
SAFETY_THRESHOLD_NAMES = {
    "block_none": "BLOCK_NONE",
    "none": "BLOCK_NONE",
    "block_only_high": "BLOCK_ONLY_HIGH",
    "high": "BLOCK_ONLY_HIGH",
    "block_medium_and_above": "BLOCK_MEDIUM_AND_ABOVE",
    "medium": "BLOCK_MEDIUM_AND_ABOVE",
    "block_low_and_above": "BLOCK_LOW_AND_ABOVE",
    "low": "BLOCK_LOW_AND_ABOVE",
    "off": "OFF",
}

TOOL_STRINGS = {
    "code_execution": ("code_execution", "ToolCodeExecution"),
    # Same wire format as the old string, so the request stays identical (newer models may prefer google_search).
    "google_search_retrieval": ("google_search_retrieval", "GoogleSearchRetrieval"),
    "google_search": ("google_search", "GoogleSearch"),
}

# Model names that only exist on the v1beta endpoint of the Gemini Developer API.
BETA_MODEL_MARKERS = ("-latest", "-preview", "-exp")


def is_old_name(qualified: str) -> bool:
    return qualified == DEV_PREFIX or qualified.startswith(DEV_PREFIX + ".") or (
        qualified == VERTEX_PREFIX or qualified.startswith(VERTEX_PREFIX + ".")
    )


def sdk_kind(qualified: str) -> str | None:
    if qualified == DEV_PREFIX or qualified.startswith(DEV_PREFIX + "."):
        return "developer"
    if qualified == VERTEX_PREFIX or qualified.startswith(VERTEX_PREFIX + "."):
        return "vertex"
    return None


def legacy_code(qualified: str) -> str:
    """Reason code for an old-SDK name the tool does not convert."""
    lowered = qualified.lower()
    if "tuned" in lowered or "tuning" in lowered:
        return "tuning-api"
    if "cach" in lowered:
        return "caches-api"
    if "file" in lowered:
        return "files-api"
    return "unsupported-api"
