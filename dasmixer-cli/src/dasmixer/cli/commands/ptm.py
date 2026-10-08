"""CLI command to update PTM configuration lists."""

import typer

from dasmixer.utils.ptm_config import update_ptm_list

app = typer.Typer(help="Update PTM configuration lists")


@app.callback(invoke_without_command=True)
def update_ptm_list_cmd() -> None:
    """Append missing PTM entries to CSV files and update LASTRUN_VERSION."""
    r, c = update_ptm_list()
    typer.echo(f"✓ renames added: {r}, ptm config added: {c}")
    typer.echo("✓ LASTRUN_VERSION updated")
