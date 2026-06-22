#!/usr/bin/env python3
"""
Generate the release body (built_apps/README.md) from built apps.
Lists each app with its 'notes' from package.ini and a download link.
"""
import configparser
import os
import sys
from pathlib import Path

RELEASE_HEADER = """# Ericsson NCOS SDK — Built Apps

Pre-built SDK applications ready for deployment. No building required.

## How to use

1. Download the `.tar.gz` file for the app you want (links below)
2. Upload to your NetCloud Manager account
3. Assign to device groups

**Documentation:** https://docs.cradlepoint.com/r/NetCloud-Manager-Tools-Tab#sdk_apps

---

## Apps

| App | Description | Download |
|-----|-------------|----------|
"""

REPO_URL = os.environ.get(
    "GITHUB_REPOSITORY_URL",
    "https://github.com/cradlepoint/sdk-samples",
)
RELEASE_TAG = "built_apps"


def parse_notes(app_dir: Path) -> str:
    """Read the 'notes' field from an app's package.ini."""
    ini_path = app_dir / "package.ini"
    if not ini_path.exists():
        return ""
    config = configparser.ConfigParser()
    config.read(ini_path, encoding="utf-8")
    for section in config.sections():
        if config.has_option(section, "notes"):
            return config.get(section, "notes").strip()
    return ""


def find_app_dir(app_name: str, apps_root: Path) -> Path | None:
    """Find the app directory matching the given name."""
    candidate = apps_root / app_name
    if candidate.is_dir():
        return candidate
    # Try case-insensitive match
    for d in apps_root.iterdir():
        if d.is_dir() and d.name.lower() == app_name.lower():
            return d
    return None


def main():
    built_dir = Path("built_apps")
    apps_root = Path("apps")

    if not built_dir.is_dir():
        print("built_apps directory not found")
        sys.exit(1)

    built_files = sorted(built_dir.glob("*.tar.gz"))
    if not built_files:
        print("No built apps found")
        sys.exit(1)

    # Determine base URL for download links
    repo_url = REPO_URL.rstrip("/")
    download_base = f"{repo_url}/releases/download/{RELEASE_TAG}"

    rows = []
    for f in built_files:
        # Extract app name from filename like "5GSpeed v0.4.0.tar.gz"
        base = f.name[:-7]  # remove .tar.gz
        app_name = base
        version = ""
        for sep in (" v", "\u00a0v", ".v"):
            if sep in base:
                app_name = base.split(sep, 1)[0]
                version = "v" + base.split(sep, 1)[1]
                break

        # Look up notes from package.ini
        notes = ""
        app_dir = find_app_dir(app_name, apps_root)
        if app_dir:
            notes = parse_notes(app_dir)

        # GitHub Releases converts spaces in asset filenames to periods
        asset_name = f.name.replace(" ", ".")
        download_link = f"[{app_name} {version}]({download_base}/{asset_name})"

        # Link app name to its source page in the repo
        app_page_name = app_dir.name if app_dir else app_name
        app_link = f"[{app_name}]({repo_url}/tree/master/apps/{app_page_name})"

        display_name = f"{app_link} {version}".strip()
        rows.append(f"| {display_name} | {notes} | {download_link} |")

    output = RELEASE_HEADER + "\n".join(rows)
    output += f"\n\n---\n\n*{len(built_files)} apps available*\n"

    with open("built_apps/README.md", "w", encoding="utf-8") as fh:
        fh.write(output)

    print(f"Generated built_apps/README.md with {len(built_files)} apps")
    sys.exit(0)


if __name__ == "__main__":
    main()
