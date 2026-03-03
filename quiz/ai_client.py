from __future__ import annotations

import os
from typing import Literal


def get_provider() -> Literal["azure", "openai"]:
    """Choose provider based on env vars.

    Azure requires:
      - AZURE_OPENAI_ENDPOINT
      - AZURE_OPENAI_API_KEY
      - AZURE_OPENAI_DEPLOYMENT
      - AZURE_OPENAI_API_VERSION (recommended)
    """
    if (
        os.getenv("AZURE_OPENAI_API_KEY")
        and os.getenv("AZURE_OPENAI_ENDPOINT")
        and os.getenv("AZURE_OPENAI_DEPLOYMENT")
    ):
        return "azure"
    return "openai"


def get_client():
    """Return an OpenAI-compatible client.

    Uses:
      - AzureOpenAI when AZURE_* vars are present
      - OpenAI otherwise
    """
    provider = get_provider()

    if provider == "azure":
        from openai import AzureOpenAI

        return AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        )

    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Set OPENAI_API_KEY for OpenAI, or AZURE_OPENAI_* vars for Azure OpenAI."
        )
    return OpenAI(api_key=api_key)


def get_model_or_deployment() -> str:
    """For Azure: deployment name. For OpenAI: model name."""
    if get_provider() == "azure":
        return os.environ["AZURE_OPENAI_DEPLOYMENT"]
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
