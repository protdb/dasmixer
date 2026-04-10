"""CLI commands for project management."""

import typer
from pathlib import Path
import asyncio
from dasmixer.api.project.project import Project
from dasmixer.api.config import config

app = typer.Typer(help="Create new project")


@app.callback(invoke_without_command=True)
def create_project(ctx: typer.Context):
    """
    Create new empty project with default Control group.
    
    The project file path is taken from parent command context.
    """
    # Get project path from parent context (main command)
    project_path = ctx.parent.params.get('file_path') if ctx.parent else None
    
    if not project_path:
        typer.echo("Error: Project path required", err=True)
        typer.echo("Usage: dasmixer path/to/project.dasmix create")
        raise typer.Exit(1)
    
    project_path = Path(project_path)
    
    # Check if file exists
    if project_path.exists():
        if not typer.confirm(f"File {project_path} exists. Overwrite?"):
            typer.echo("Cancelled")
            raise typer.Exit(0)
        project_path.unlink()
    
    # Create project
    async def _create():
        async with Project(path=project_path, create_if_not_exists=True) as project:
            # Create default Control group
            await project.add_subset(
                "Control",
                details="Default control group",
                display_color="#3B82F6"  # Blue
            )
            typer.echo(f"✓ Created project: {project_path}")
            typer.echo("✓ Added default group: Control")
    
    try:
        asyncio.run(_create())
        
        # Add to recent projects
        config.add_recent_project(str(project_path))
        
    except Exception as e:
        typer.echo(f"Error creating project: {e}", err=True)
        raise typer.Exit(1)
