from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable

from rich.console import Console

from curai.agent.prompts import build_system_prompt
from curai.config import CliConfig
from curai.llm.client import LlmClient
from curai.tools.executor import ToolExecutor, openai_tool_schemas

console = Console()


def _format_tool_call(name: str, arguments: dict[str, Any]) -> str:
    preview = ", ".join(f"{k}={v!r}"[:80] for k, v in list(arguments.items())[:4])
    return f"{name}({preview})"


async def run_agent(
    *,
    prompt: str,
    workspace: Path,
    config: CliConfig,
    history: list[dict[str, str]] | None = None,
    approve: Callable[[str, dict[str, Any]], bool] | None = None,
) -> str:
    workspace = workspace.resolve()
    llm = LlmClient(config.llm)
    tools = openai_tool_schemas()
    executor = ToolExecutor(workspace, permission_mode=config.permission_mode, approve=approve)

    messages: list[dict[str, Any]] = [{"role": "system", "content": build_system_prompt(workspace)}]
    for item in history or []:
        role = item.get("role") or "user"
        content = (item.get("content") or "").strip()
        if content and role in {"user", "assistant"}:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})

    for step in range(1, config.max_agent_steps + 1):
        response = await llm.chat_with_tools(messages=messages, tools=tools)

        if not response.tool_calls:
            if response.content:
                return response.content
            return "Agent finished without a response."

        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments) if config.llm.provider == "openai" else call.arguments,
                    },
                }
                for call in response.tool_calls
            ],
        }
        messages.append(assistant_message)

        for call in response.tool_calls:
            console.print(f"[dim]step {step}[/dim] [cyan]{_format_tool_call(call.name, call.arguments)}[/cyan]")
            result = executor.execute(call.name, call.arguments)
            if result.error:
                console.print(f"[yellow]{result.output[:500]}[/yellow]")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result.output,
                }
            )

    for message in reversed(messages):
        if message.get("role") == "assistant" and message.get("content"):
            return str(message["content"])
    return "Agent reached max steps without a final answer."


def run_agent_sync(**kwargs: Any) -> str:
    return asyncio.run(run_agent(**kwargs))
