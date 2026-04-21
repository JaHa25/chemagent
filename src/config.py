"""Central configuration: loads .env and exposes constants."""

import os
import warnings
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
MAX_STEPS: int = int(os.environ.get("CHEMAGENT_MAX_STEPS", "8"))

if not ANTHROPIC_API_KEY:
    warnings.warn(
        "ANTHROPIC_API_KEY is not set. "
        "Cloud (Anthropic) profiles will fail at runtime; "
        "local Ollama/LM Studio profiles are unaffected.",
        stacklevel=1,
    )
