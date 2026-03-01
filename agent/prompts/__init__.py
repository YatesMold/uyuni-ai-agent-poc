import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent


def _resolve_prompt_path(filename: str) -> Path:
    """Resolve a prompt filename to an absolute path within the prompts directory."""
    return _PROMPTS_DIR / filename


def load_prompt(filename: str) -> str:
    """Load a prompt template from a text file in the prompts directory.

    Resolves paths relative to ``agent/prompts/``, not the working directory.

    Args:
        filename: Name of the prompt file (e.g. ``"system_prompt.md"``).

    Returns:
        The prompt text with leading/trailing whitespace stripped.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    path = _resolve_prompt_path(filename)
    if not path.is_file():
        raise FileNotFoundError(
            f"Prompt file not found: {path.resolve()}. "
            f"Ensure '{filename}' exists in the agent/prompts/ directory."
        )
    logger.debug("Loading prompt from %s", path)
    return path.read_text(encoding="utf-8").strip()


def build_prompt(scenario: str, context: dict) -> str:
    """Compose a scenario-specific user prompt with interpolated context.

    Loads the scenario template (e.g. ``high_cpu.md``), substitutes
    ``{minion_id}``, ``{metric_value}``, ``{threshold}`` from *context*,
    and appends ``raw_output`` after the ``--- RAW SYSTEM OUTPUT ---`` marker.

    Args:
        scenario: Scenario name without extension (e.g. ``"high_cpu"``).
        context: Dict containing at least ``minion_id``, ``metric_value``,
                 ``threshold``, and ``raw_output``.

    Returns:
        The fully composed user-message string.

    Raises:
        FileNotFoundError: If the scenario template does not exist.
        KeyError: If *context* is missing a required placeholder.
    """
    template = load_prompt(f"{scenario}.md")
    raw_output = context["raw_output"]
    interpolated = template.format(**context)
    return f"{interpolated}\n{raw_output}\n--- END OUTPUT ---"
