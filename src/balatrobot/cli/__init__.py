"""CLI entry point for BalatroBot."""

import typer

from balatrobot.cli.api import api
from balatrobot.cli.serve import serve

app = typer.Typer(
    name="balatrobot",
    help="BalatroBot - personal Balatro play setup with API and helpers",
    no_args_is_help=True,
)

# Register commands
app.command()(serve)
app.command()(api)


def main() -> None:
    """Entry point for balatrobot CLI."""
    app()
