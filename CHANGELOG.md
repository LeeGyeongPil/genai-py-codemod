# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-19

### Added

- `genai-py-codemod PATH...`: format-preserving (libcst) migration of `google-generativeai` and
  `vertexai.generative_models` code to `google-genai`. Prints a diff by default, `--write` applies it,
  `--check` exits 1 when a file would change or a manual spot remains, `--report json` for CI.
- Conversions: imports, `configure` / `vertexai.init` to `genai.Client(...)`, model handles to model names plus a
  `types.GenerateContentConfig`, `generate_content` (stream and async), `start_chat` / `send_message`,
  `count_tokens`, `embed_content`, `generation_config` dicts and classes, safety settings, built-in tool strings.
- Manual-point report with file:line and reason codes. A file is migrated completely or not at all.
- `--api-version auto|keep|none` for the default API version change in google-genai 3.0.
- `genai-py-codemod verify BEFORE AFTER`: runs both files against mocked transports (no key, no network) and compares
  the API requests; cross-interpreter mode with `--old-python` / `--new-python`.
- Public Python API: `migrate_source`, `verify_files`. `VerifyRunError.code` (one of 8 codes) and
  `error.message()`, `VerifyResult.version_changes`; `verify --json` failures print `error` (code) and `message`.
- English and Korean messages (`--lang en|ko`, `GENAI_PY_CODEMOD_LANG`, `LANG`).
