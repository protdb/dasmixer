"""CLI commands for managing project tools."""

import json
import typer
from pathlib import Path
from typing import Annotated
import asyncio
from dasmixer.api.project.project import Project

app = typer.Typer(help="Manage project tools")


@app.command()
def add(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    name: Annotated[str, typer.Option("--name", "-n", help="Tool name")] = ...,
    parser: Annotated[str, typer.Option("--parser", "-p", help="Parser name (e.g., PowerNovo2, MGF)")] = ...,
    type: Annotated[str, typer.Option("--type", "-t", help="Tool type: Library or De Novo")] = "Library",
    color: Annotated[str, typer.Option("--color", help="Display color (hex, e.g. #4CAF50)")] = None,
):
    """
    Add a new tool to the project.
    """
    if type not in ("Library", "De Novo"):
        typer.echo("Error: --type must be 'Library' or 'De Novo'", err=True)
        raise typer.Exit(1)

    async def _run():
        async with Project(path=Path(project_path), create_if_not_exists=False) as project:
            tools = await project.get_tools()
            if any(t.name == name for t in tools):
                typer.echo(f"Error: Tool '{name}' already exists", err=True)
                raise typer.Exit(1)
            await project.add_tool(
                name=name,
                type=type,
                parser=parser,
                settings={},
                display_color=color,
            )
            await project.save()
            typer.echo(f"✓ Tool added: {name} (parser: {parser}, type: {type})")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def configure(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    name: Annotated[str, typer.Option("--name", "-n", help="Tool name")] = ...,
    key: Annotated[str, typer.Option("--key", "-k", help="Setting key")] = ...,
    value: Annotated[str, typer.Option("--value", "-v", help="Setting value")] = ...,
):
    """
    Configure a tool setting.
    """
    async def _run():
        async with Project(path=Path(project_path), create_if_not_exists=False) as project:
            tools = await project.get_tools()
            tool = next((t for t in tools if t.name == name), None)
            if not tool:
                typer.echo(f"Error: Tool '{name}' not found", err=True)
                raise typer.Exit(1)
            settings = dict(tool.settings or {})
            settings[key] = value
            await project._execute(
                "UPDATE tool SET settings=? WHERE id=?",
                [json.dumps(settings), tool.id],
            )
            await project.save()
            typer.echo(f"✓ Tool '{name}' configured: {key} = {value}")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command(name="param-list")
def param_list(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    name: Annotated[str, typer.Option("--name", "-n", help="Filter by tool name")] = None,
):
    """
    List tool parameters/settings.
    """
    async def _run():
        async with Project(path=Path(project_path), create_if_not_exists=False) as project:
            tools = await project.get_tools()
            if name:
                tools = [t for t in tools if t.name == name]
                if not tools:
                    typer.echo(f"Error: Tool '{name}' not found", err=True)
                    raise typer.Exit(1)
            for tool in tools:
                typer.echo(f"\nTool: {tool.name} ({tool.parser}, {tool.type})")
                settings = tool.settings or {}
                if settings:
                    for k, v in settings.items():
                        typer.echo(f"  {k:<20} = {v}")
                else:
                    typer.echo("  (no settings)")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def list(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
):
    """
    List all tools in the project.
    """
    async def _run():
        async with Project(path=Path(project_path), create_if_not_exists=False) as project:
            tools = await project.get_tools()
            if not tools:
                typer.echo("No tools found.")
                return
            typer.echo(f"{'ID':<5} {'Name':<20} {'Type':<12} {'Parser':<20} {'Settings'}")
            typer.echo("-" * 70)
            for t in tools:
                settings_count = len(t.settings or {})
                typer.echo(f"{t.id:<5} {t.name:<20} {t.type:<12} {t.parser:<20} {settings_count} keys")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
