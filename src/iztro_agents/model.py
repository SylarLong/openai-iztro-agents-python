"""Factory for the hosted Ziwei model as a stock OpenAI Agents SDK model."""

from __future__ import annotations

import os

from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

DEFAULT_BASE_URL = "https://chat-api.iztro.com"
IZTRO_ZIWEI_MODEL = "iztro-ziwei-v3"


def iztro_ziwei_model(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str = IZTRO_ZIWEI_MODEL,
) -> OpenAIChatCompletionsModel:
    """Build the hosted Ziwei agent as a stock ``OpenAIChatCompletionsModel``.

    The iztro chart tools run inside this model on the server (hidden). ``api_key`` /
    ``base_url`` fall back to ``ZIWEI_API_KEY`` / ``ZIWEI_BASE_URL``.

        from agents import Agent, Runner
        from iztro_agents import iztro_ziwei_model

        agent = Agent(name="Ziwei", model=iztro_ziwei_model(api_key=KEY), tools=[...])
        await Runner.run(agent, "…")
    """
    api_key = api_key or os.environ.get("ZIWEI_API_KEY")
    if not api_key:
        raise ValueError("api_key is required (pass api_key=... or set ZIWEI_API_KEY)")
    base = (base_url or os.environ.get("ZIWEI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    client = AsyncOpenAI(base_url=f"{base}/v2", api_key=api_key)
    return OpenAIChatCompletionsModel(model=model, openai_client=client)
