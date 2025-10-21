import os
from typing import Tuple, overload

from dotenv import load_dotenv

# Ollama Configuration (Only LLM provider)
DEFAULT_OLLAMA_BASE_URL = "http://ollama:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:1b"


@overload
def require_all_env(key: str) -> str: ...
@overload
def require_all_env(*keys: str) -> Tuple[str, ...]: ...


def require_all_env(*keys: str) -> str | Tuple[str, ...]:  # type: ignore
    load_dotenv(override=True)

    values: list[str] = []
    missing: list[str] = []

    for key in keys:
        val = os.getenv(key)
        if val is None:
            missing.append(key)
        else:
            values.append(val)

    if missing:
        raise OSError(f"Missing required environment variable(s): {', '.join(missing)}")

    return tuple(values) if len(values) > 1 else values[0]


@overload
def require_any_env(key: str) -> str | None: ...
@overload
def require_any_env(*keys: str) -> Tuple[str | None, ...]: ...


def require_any_env(*keys: str) -> str | None | Tuple[str | None, ...]:  # type: ignore
    load_dotenv(override=True)

    values: list[str | None] = []
    for key in keys:
        val = os.getenv(key)
        values.append(val)

    if all(v is None for v in values):
        raise OSError(
            f"At least one of the required environment variables must be set: {', '.join(keys)}"
        )

    return tuple(values) if len(values) > 1 else values[0]


def get_ollama_config() -> tuple[str, str]:
    """Get Ollama configuration (base_url, model)."""
    load_dotenv(override=True)
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    return base_url, model
