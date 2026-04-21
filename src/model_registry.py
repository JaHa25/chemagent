"""
Loads models.yaml and resolves named model profiles.

Usage:
    registry = ModelRegistry()
    profile = registry.get("claude_haiku")
    # → ModelProfile(model_id=..., api_key=..., api_base=None, ...)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ModelProfile:
    name: str
    label: str
    provider: str
    model_id: str
    api_key: str
    api_base: Optional[str] = None
    max_steps: Optional[int] = None


_ENV_RE = re.compile(r"^\$\{(\w+)\}$")


def _resolve_key(raw: str) -> str:
    """Expand '${VAR}' → env value; return raw string otherwise."""
    m = _ENV_RE.match(raw.strip())
    if m:
        var = m.group(1)
        value = os.environ.get(var, "")
        if not value:
            import warnings
            warnings.warn(
                f"models.yaml api_key references ${{{var}}} but the variable is not set. "
                "This profile will fail at runtime.",
                stacklevel=3,
            )
        return value
    return raw


class ModelRegistry:
    _DEFAULT_YAML = Path(__file__).parent.parent / "models.yaml"

    def __init__(self, yaml_path: Path | None = None):
        path = yaml_path or self._DEFAULT_YAML
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        self._profiles: dict[str, ModelProfile] = {}
        for name, cfg in data.get("profiles", {}).items():
            self._profiles[name] = ModelProfile(
                name=name,
                label=cfg.get("label", name),
                provider=cfg.get("provider", "unknown"),
                model_id=cfg["model_id"],
                api_key=_resolve_key(cfg.get("api_key", "")),
                api_base=cfg.get("api_base"),
                max_steps=cfg.get("max_steps"),
            )

        self._default = data.get("default_profile", next(iter(self._profiles)))

    def get(self, name: str) -> ModelProfile:
        if name not in self._profiles:
            raise ValueError(
                f"Unknown model profile '{name}'. "
                f"Available: {sorted(self._profiles)}"
            )
        return self._profiles[name]

    def default_name(self) -> str:
        """CHEMAGENT_PROFILE env var overrides models.yaml default_profile."""
        return os.environ.get("CHEMAGENT_PROFILE", self._default)

    def all_profiles(self) -> dict[str, ModelProfile]:
        return dict(self._profiles)

    def dropdown_choices(self) -> list[str]:
        return list(self._profiles)
