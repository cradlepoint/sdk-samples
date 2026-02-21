#!/usr/bin/env python3
"""
Update the main README.md with download links to built apps from the release.
Run after a release is published - adds a link under each app's description.
"""
import os
import re
import sys
from pathlib import Path


def get_built_apps(built_apps_dir: str) -> dict:
    """Return dict mapping lowercase app name -> actual filename.
    Handles versioned names like '5GSpeed v1.0.0.tar.gz' - maps to base name '5gspeed'.
    """
    built = {}
    for f in Path(built_apps_dir).glob("*.tar.gz"):
        # Remove .tar.gz
        base = f.name[:-7]
        # Extract app name: "5GSpeed v1.0.0" or "5GSpeed\xa0v1.0.0" (nb space) -> "5GSpeed"
        for sep in (" v", "\u00a0v", ".v"):  # space, non-breaking space, or dot (GitHub converts spaces)
            if sep in base:
                app_base = base.split(sep, 1)[0]
                break
        else:
            app_base = base
        key = app_base.lower()
        built[key] = f.name
    return built


def normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def update_readme(readme_path: str, built_apps_dir: str, release_base_url: str) -> bool:
    """
    Add download links under each built app's description in the README.
    Returns True if README was modified.
    """
    built = get_built_apps(built_apps_dir)
    if not built:
        print("No built apps found, skipping README update")
        return False
    print(f"Found {len(built)} built apps")

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = normalize_line_endings(content)

    # Match app blocks: "- **AppName**" followed by description lines (indented with - or tab)
    # Description lines are: "    - " or "\t- " or continuation of previous
    app_header = re.compile(r'^- \*\*([^*]+)\*\*\s*$', re.MULTILINE)

    lines = content.split("\n")
    result = []
    i = 0
    modified = False
    in_app_section = False
    links_added = 0
    skipped_not_built = 0

    while i < len(lines):
        line = lines[i]
        result.append(line)
        # Only process app headers within Sample Application Descriptions section
        if line.strip() == "## Sample Application Descriptions":
            in_app_section = True
        elif in_app_section and (line.strip() == "----------" or (line.startswith("## ") and "Sample Application Descriptions" not in line)):
            in_app_section = False
        m = app_header.match(line) if in_app_section else None
        if m:
            app_name_readme = m.group(1).strip()
            app_key = app_name_readme.lower()
            has_download_link = False
            # Collect description lines (next lines that are indented)
            i += 1
            while i < len(lines):
                next_line = lines[i]
                # Stop at next app header (starts with "- **") or section end
                if re.match(r'^- \*\*', next_line):
                    break
                if next_line.strip() == "----------" or next_line.startswith("## "):
                    break
                if not next_line.strip():  # empty line might be within description
                    result.append(next_line)
                    i += 1
                    continue
                # Skip existing download lines - we'll replace with correct link below
                if "**Download:**" in next_line:
                    has_download_link = True
                    i += 1
                    continue
                # This is part of the description
                result.append(next_line)
                i += 1
            # Always add/replace download link if this app was built
            if app_key in built:
                filename = built[app_key]
                # GitHub converts " v" to ".v" in release assets - use dot in URL for working links
                url_filename = filename.replace(" v", ".v")
                url = f"{release_base_url}/{url_filename}"
                link_line = f"    - **Download:** [{filename}]({url})"
                result.append(link_line)
                modified = True
                if has_download_link:
                    links_added += 1
                    print(f"  Replaced link for {app_name_readme}")
                else:
                    links_added += 1
                    print(f"  Added link for {app_name_readme}")
            else:
                skipped_not_built += 1
            i -= 1  # We consumed one extra - backtrack so next iteration sees the header
        i += 1

    print(f"Summary: added/replaced {links_added}, skipped (not built) {skipped_not_built}")
    if modified:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("\n".join(result) + "\n")
        return True
    return False


def main():
    repo = os.environ.get("GITHUB_REPOSITORY", "cradlepoint/sdk-samples")
    release_base_url = f"https://github.com/{repo}/releases/download/built_apps"
    readme_path = "README.md"
    built_apps_dir = "built_apps"

    if not os.path.isdir(built_apps_dir):
        print(f"built_apps directory not found")
        sys.exit(1)

    changed = update_readme(readme_path, built_apps_dir, release_base_url)
    if changed:
        print("README.md updated with download links")
    else:
        print("No changes to README.md")
    sys.exit(0)


if __name__ == "__main__":
    main()
