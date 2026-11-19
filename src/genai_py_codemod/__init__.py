"""genai-py-codemod: move google-generativeai / vertexai.generative_models code to google-genai.

Public API:

* :func:`migrate_source` - rewrite one source string (needs only ``libcst``)
* :func:`verify_files` - compare the API requests of two files against mocked transports
"""

from __future__ import annotations

__version__ = "0.1.0"

from .migrate import MigrationResult, ParseError, migrate_source  # noqa: E402
from .report import Finding  # noqa: E402
from .verify import VerifyResult, VerifyRunError, verify_files  # noqa: E402

__all__ = [
    "Finding",
    "MigrationResult",
    "ParseError",
    "VerifyResult",
    "VerifyRunError",
    "__version__",
    "migrate_source",
    "verify_files",
]
