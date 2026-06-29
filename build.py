#!/usr/bin/env python3
"""
build.py — DASMixer unified build script.

Commands:
    set-version <version>   — Update version in all project files
    pypi [version] [--prod] — Build and upload Python packages to PyPI
    internal [version]      — Build Windows installer (Windows only)
    release <version>       — Full release pipeline
"""

import re
import sys
import subprocess
import zipfile
import urllib.request
import urllib.error
import time
from pathlib import Path
from typing import Optional

import typer

REPO_ROOT = Path(__file__).resolve().parent
PACKAGES = ["dasmixer-core", "dasmixer-gui", "dasmixer-cli", "metapackage"]
PYPI_PACKAGE_NAMES = ["dasmixer-core", "dasmixer-gui", "dasmixer-cli", "dasmixer"]
ISCC_PATH = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
CHANGELOG_DIR = REPO_ROOT / "docs" / "project" / "changes"

app = typer.Typer(help="DASMixer unified build script.")


def get_current_version() -> str:
    pyproject_path = REPO_ROOT / "dasmixer-core" / "pyproject.toml"
    text = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        typer.echo("Error: version not found in dasmixer-core/pyproject.toml", err=True)
        raise typer.Exit(1)
    return match.group(1)


def validate_version(version: str) -> None:
    if not re.match(r'^\d+\.\d+\.\d+', version):
        typer.echo(f"Error: invalid version format: {version}", err=True)
        raise typer.Exit(1)


def set_version(version: str) -> None:
    try:
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "build_tools" / "set_version.py"), version],
            check=True,
        )
    except subprocess.CalledProcessError:
        raise typer.Exit(1)


def build_python_packages() -> list[Path]:
    artifacts: list[Path] = []
    for pkg in PACKAGES:
        typer.echo(f"--- Building {pkg} ---")
        subprocess.run(["poetry", "build"], cwd=REPO_ROOT / pkg, check=True)
        typer.echo(f"✓ {pkg} built successfully")
    for pkg in PACKAGES:
        dist_dir = REPO_ROOT / pkg / "dist"
        for f in dist_dir.glob("*"):
            if f.suffix in (".whl", ".tar.gz"):
                artifacts.append(f)
    if not artifacts:
        typer.echo("Error: No build artifacts found", err=True)
        raise typer.Exit(1)
    return artifacts


def check_artifacts(artifacts: list[Path]) -> None:
    for pkg in PACKAGES:
        if not any(f"/{pkg}/dist/" in a.as_posix() for a in artifacts):
            typer.echo(f"Error: no artifacts found for {pkg}", err=True)
            raise typer.Exit(1)


def upload_to_testpypi(artifacts: list[Path]) -> None:
    subprocess.run(["twine", "upload", "--repository", "testpypi", *map(str, artifacts)], check=True)


def upload_to_pypi(artifacts: list[Path]) -> None:
    subprocess.run(["twine", "upload", *map(str, artifacts)], check=True)


def check_testpypi_availability(version: str, timeout_sec: int = 120) -> None:
    for name in PYPI_PACKAGE_NAMES:
        url = f"https://test.pypi.org/pypi/{name}/{version}/json"
        start = time.monotonic()
        while time.monotonic() - start < timeout_sec:
            try:
                resp = urllib.request.urlopen(url)
                if resp.status == 200:
                    break
            except urllib.error.HTTPError:
                pass
            elapsed = int(time.monotonic() - start)
            typer.echo(f"  Waiting for {name} {version} on TestPyPI... ({elapsed}s)")
            time.sleep(5)
        else:
            typer.echo(f"Error: {name} {version} not available on TestPyPI after {timeout_sec}s", err=True)
            raise typer.Exit(1)


def build_windows_installer(version: str) -> Path:
    subprocess.run(["pyinstaller", "dasmixer.spec", "--clean", "-y"], cwd=REPO_ROOT, check=True)
    exe_path = REPO_ROOT / "dist" / "dasmixer" / "dasmixer.exe"
    if not exe_path.exists():
        typer.echo("Error: dasmixer.exe not found after PyInstaller build", err=True)
        raise typer.Exit(1)
    subprocess.run([ISCC_PATH, "dasmixer.iss"], cwd=REPO_ROOT, check=True)
    installer_path = REPO_ROOT / "dist" / "setup" / f"DASMixer{version}-setup.exe"
    if not installer_path.exists():
        typer.echo(f"Error: Installer not found: {installer_path}", err=True)
        raise typer.Exit(1)
    return installer_path


def archive_installer(exe_path: Path) -> Path:
    zip_path = exe_path.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_path, exe_path.name)
    return zip_path


def create_github_release(version: str, exe_path: Path, artifacts: list[Path]) -> str:
    changelog_path = CHANGELOG_DIR / f"v{version}.md"
    if not changelog_path.exists():
        typer.echo(f"Error: Changelog not found: {changelog_path}", err=True)
        raise typer.Exit(1)
    subprocess.run(
        [
            "gh", "release", "create",
            f"v{version}",
            "--title", f"DASMixer v{version}",
            "--notes-file", str(changelog_path),
            str(exe_path),
            *map(str, artifacts),
        ],
        cwd=REPO_ROOT,
        check=True,
    )
    result = subprocess.run(
        ["gh", "release", "view", f"v{version}", "--json", "url", "--jq", ".url"],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT,
    )
    return result.stdout.strip()


@app.command("set-version")
def cmd_set_version(
    version: str = typer.Argument(..., help="New version string (e.g. 0.6.0)")
):
    validate_version(version)
    set_version(version)
    typer.echo(f"Version updated to {version}")


@app.command("pypi")
def cmd_pypi(
    version: Optional[str] = typer.Argument(None, help="Set version before building"),
    prod: bool = typer.Option(False, "--prod", help="Upload to production PyPI"),
):
    if version:
        validate_version(version)
        set_version(version)
    artifacts = build_python_packages()
    check_artifacts(artifacts)
    if prod:
        upload_to_pypi(artifacts)
        typer.echo("")
        for name in PYPI_PACKAGE_NAMES:
            typer.echo(f"  https://pypi.org/project/{name}/")
    else:
        upload_to_testpypi(artifacts)
        typer.echo("")
        for name in PYPI_PACKAGE_NAMES:
            typer.echo(f"  https://test.pypi.org/project/{name}/")


@app.command("internal")
def cmd_internal(
    version: Optional[str] = typer.Argument(None, help="Set version before building"),
):
    if sys.platform != "win32":
        typer.echo("Error: 'internal' command is only available on Windows.", err=True)
        raise typer.Exit(1)
    if version:
        validate_version(version)
        set_version(version)
    current_version = get_current_version()
    exe_path = build_windows_installer(current_version)
    zip_path = archive_installer(exe_path)
    typer.echo("")
    typer.echo(f"Installer: {exe_path}")
    typer.echo(f"Archive:   {zip_path}")


@app.command("release")
def cmd_release(
    version: str = typer.Argument(..., help="Version to release (e.g. 0.6.0)"),
):
    # --- Step 0: Validation ---
    validate_version(version)
    current_version = get_current_version()

    if version == current_version:
        if not typer.confirm(f"Version {version} is already set. Release without bumping?"):
            raise typer.Exit(0)

    changelog_path = CHANGELOG_DIR / f"v{version}.md"
    if not changelog_path.exists():
        typer.echo(f"Error: Changelog not found: {changelog_path}", err=True)
        raise typer.Exit(1)

    if not typer.confirm(f"You are about to publish DASMixer v{version} to GitHub and PyPI. Proceed?"):
        raise typer.Exit(0)

    # --- Step 1: Update version ---
    typer.echo("")
    typer.echo("=== Updating version ===")
    if version != current_version:
        set_version(version)

    # --- Step 2: Build Python packages ---
    typer.echo("")
    typer.echo("=== Building Python packages ===")
    artifacts = build_python_packages()
    check_artifacts(artifacts)

    # --- Step 3: Windows + GitHub release ---
    typer.echo("")
    release_url = None
    if sys.platform == "win32":
        typer.echo("=== Building Windows installer ===")
        exe_path = build_windows_installer(version)
        typer.echo("")
        typer.echo("=== Creating GitHub release ===")
        release_url = create_github_release(version, exe_path, artifacts)
    else:
        typer.echo("Skipping Windows build (not on Windows).")

    # --- Step 4: TestPyPI ---
    typer.echo("")
    typer.echo("=== Uploading to TestPyPI ===")
    upload_to_testpypi(artifacts)
    check_testpypi_availability(version)

    # --- Step 5: PyPI (prod) ---
    typer.echo("")
    typer.echo("=== Uploading to PyPI (production) ===")
    upload_to_pypi(artifacts)

    # --- Step 6: Summary ---
    typer.echo("")
    typer.echo(f"=== Release DASMixer v{version} complete ===")
    typer.echo("")
    if release_url:
        typer.echo(f"  GitHub Release: {release_url}")
    typer.echo(f"  PyPI:           https://pypi.org/project/dasmixer/{version}/")


if __name__ == "__main__":
    app()
