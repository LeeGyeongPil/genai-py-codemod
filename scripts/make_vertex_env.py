"""Create .venv-vertex with the old Vertex AI SDK (google-cloud-aiplatform 2.10.0) for the cross-interpreter check.

google-cloud-aiplatform pins google-genai<3, so it cannot live in the same environment as google-genai 3.x.
`genai-py-codemod verify --old-python .venv-vertex/bin/python` runs the "before" file there and the "after" file in
the normal environment.

Usage: uv run python scripts/make_vertex_env.py   (needs uv and network access; takes about 10 seconds)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

AIPLATFORM = "google-cloud-aiplatform==2.10.0"
ENV = Path(__file__).resolve().parent.parent / ".venv-vertex"


def main() -> int:
    python = ENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.exists():
        subprocess.run(["uv", "venv", "--python", "3.12", str(ENV)], check=True)
    subprocess.run(["uv", "pip", "install", "--python", str(python), AIPLATFORM], check=True)
    print(f"Vertex environment ready: {python}")
    print(f"For the tests: export GENAI_PY_CODEMOD_VERTEX_PYTHON={python}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
