from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import httpx
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from curai import __version__
from curai.agent.loop import run_agent_sync
from curai.auth import auth_app
from curai.config import CliConfig, CONFIG_FILE, load_config

app = typer.Typer(
    name="curai",
    help="CurAI CLI — agentic coding from natural language prompts.",
    no_args_is_help=False,
)
app.add_typer(auth_app, name="auth")
console = Console()


def _default_approve(tool_name: str, arguments: dict[str, Any]) -> bool:
    console.print(Panel(f"[bold]{tool_name}[/bold]\n{arguments}", title="Approve tool?", border_style="yellow"))
    return typer.confirm("Run this tool?", default=False)


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="Show version and exit"),
) -> None:
    if version:
        typer.echo(f"curai {__version__}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        ctx.invoke(chat)


@app.command("ask")
def ask(
    prompt: str = typer.Argument(..., help="Natural language coding task"),
    permission: Optional[str] = typer.Option(None, "--permission", "-p", help="auto|ask|plan"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model name"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace", "-C", help="Project root"),
) -> None:
    """Run one agentic coding task and print the result."""
    _run_prompt(prompt, workspace=workspace, permission=permission, model=model)


@app.command("chat")
def chat(
    permission: Optional[str] = typer.Option(None, "--permission", "-p", help="auto|ask|plan"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model name"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace", "-C", help="Project root"),
) -> None:
    """Interactive REPL — each prompt runs the coding agent."""
    config = _resolve_config(permission=permission, model=model)
    history: list[dict[str, str]] = []
    workspace = workspace.resolve()
    console.print(Panel(f"CurAI coding agent\nWorkspace: {workspace}\nModel: {config.llm.model}", border_style="green"))
    console.print("Type a task, or 'exit' / Ctrl-D to quit.\n")
    while True:
        try:
            line = console.input("[bold blue]you>[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not line:
            continue
        if line.lower() in {"exit", "quit", "/exit"}:
            break
        try:
            answer = run_agent_sync(
                prompt=line,
                workspace=workspace,
                config=config,
                history=history,
                approve=_default_approve if config.permission_mode != "auto" else None,
            )
            history.append({"role": "user", "content": line})
            history.append({"role": "assistant", "content": answer})
            console.print()
            console.print(Markdown(answer))
            console.print()
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")


@app.command("config")
def config_show() -> None:
    """Show effective configuration."""
    loaded = load_config()
    console.print(f"Config file: {CONFIG_FILE}")
    console.print(f"LLM: {loaded.llm.provider} {loaded.llm.model} @ {loaded.llm.base_url}")
    console.print(f"Permission: {loaded.permission_mode}")
    console.print(f"Max steps: {loaded.max_agent_steps}")
    console.print(f"CurAI API: {loaded.curai_api.base_url}")


def _resolve_config(
    *,
    permission: Optional[str],
    model: Optional[str],
) -> CliConfig:
    config = load_config()
    if permission:
        mode = permission.strip().lower()
        if mode in {"auto", "ask", "plan"}:
            config.permission_mode = mode  # type: ignore[assignment]
    if model:
        config.llm.model = model
    return config


def _run_prompt(
    prompt: str,
    *,
    workspace: Path,
    permission: Optional[str],
    model: Optional[str],
) -> None:
    config = _resolve_config(permission=permission, model=model)
    try:
        answer = run_agent_sync(
            prompt=prompt,
            workspace=workspace.resolve(),
            config=config,
            approve=_default_approve if config.permission_mode != "auto" else None,
        )
    except httpx.HTTPError as exc:
        console.print(f"[red]LLM request failed:[/red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print(Markdown(answer))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
