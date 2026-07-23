from __future__ import annotations

import httpx
import typer

from curai.config import load_config, save_config, save_token

auth_app = typer.Typer(help="Authentication for CurAI API (optional).")


@auth_app.command("login")
def login(
    email: str = typer.Option("dev@localhost", "--email", "-e", help="Email for /auth/token"),
    base_url: str | None = typer.Option(None, "--base-url", help="CurAI API base URL"),
) -> None:
    """Store a JWT from the CurAI backend."""
    config = load_config()
    api_base = (base_url or config.curai_api.base_url).rstrip("/")
    with httpx.Client(timeout=30.0) as client:
        response = client.post(f"{api_base}/auth/token", json={"email": email})
        response.raise_for_status()
        token = response.json().get("access_token")
    if not token:
        typer.echo("No access_token in response", err=True)
        raise typer.Exit(1)
    save_token(str(token))
    config.curai_api.base_url = api_base
    save_config(config)
    typer.echo(f"Saved token for {api_base}")
