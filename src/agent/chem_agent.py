"""Builds and returns a ChemAgent instance (ToolCallingAgent or CodeAgent)."""

from smolagents import ToolCallingAgent, CodeAgent, LiteLLMModel

from ..config import MAX_STEPS
from ..model_registry import get_registry
from ..agent.system_prompt import SYSTEM_PROMPT
from ..tools.summary_statistics import summary_statistics
from ..tools.detect_anomalies import detect_anomalies
from ..tools.compute_trend import compute_trend
from ..tools.compare_pre_post_event import compare_pre_post_event
from ..tools.plot_variable import plot_variable

TOOLS = [
    summary_statistics,
    detect_anomalies,
    compute_trend,
    compare_pre_post_event,
    plot_variable,
]

_LOCAL_PROVIDERS = {"ollama", "lmstudio"}


def build_agent(model_profile: str | None = None):
    """Instantiate and return a fresh ChemAgent for the given model profile.

    Uses ToolCallingAgent for cloud models (Anthropic) and CodeAgent for local
    models (Ollama, LM Studio) since smaller open-source models often don't
    reliably follow native function-calling formats.

    Args:
        model_profile: Name of a profile in models.yaml (e.g. "claude_haiku",
            "local_gemma4_e4b"). Defaults to the registry default.
    """
    registry = get_registry()
    profile_name = model_profile or registry.default_name()
    profile = registry.get(profile_name)

    litellm_kwargs: dict = {
        "model_id": profile.model_id,
        "api_key":  profile.api_key,
    }
    if profile.api_base:
        litellm_kwargs["api_base"] = profile.api_base

    model = LiteLLMModel(**litellm_kwargs)
    effective_max_steps = profile.max_steps if profile.max_steps is not None else MAX_STEPS

    if profile.provider in _LOCAL_PROVIDERS:
        return CodeAgent(
            tools=TOOLS,
            model=model,
            max_steps=effective_max_steps,
            instructions=SYSTEM_PROMPT,
        )

    return ToolCallingAgent(
        tools=TOOLS,
        model=model,
        max_steps=effective_max_steps,
        instructions=SYSTEM_PROMPT,
    )
