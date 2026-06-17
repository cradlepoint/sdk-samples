#!/usr/bin/env python3
"""
Generate the release body (built_apps/README.md) from the app catalog.
Lists all built apps with their descriptions.
"""
import json
import os
import sys
from pathlib import Path

RELEASE_HEADER = """# Ericsson NCOS SDK — Built Apps

These are pre-built SDK applications ready for deployment. No modification or building required.

## How to use these files

1. Download the `.tar.gz` file for the app you want
2. Upload to your NetCloud Manager account
3. Assign to device groups

**Documentation:** https://docs.cradlepoint.com/r/NetCloud-Manager-Tools-Tab#sdk_apps

**App Store:** Browse all apps with details at the [NCOS SDK App Store](https://cradlepoint.github.io/sdk-samples/)

---

## Apps

"""


def main():
    built_dir = Path("built_apps")
    if not built_dir.is_dir():
        print("built_apps directory not found")
        sys.exit(1)

    # Get list of built tar.gz files
    built_files = sorted(built_dir.glob("*.tar.gz"))

    output = [RELEASE_HEADER]
    for f in built_files:
        # Extract app name from filename like "5GSpeed v0.4.0.tar.gz"
        base = f.name[:-7]  # remove .tar.gz
        for sep in (" v", "\u00a0v", ".v"):
            if sep in base:
                app_name = base.split(sep, 1)[0]
                version = base.split(sep, 1)[1]
                break
        else:
            app_name = base
            version = ""

        if version:
            output.append(f"- **{app_name}** v{version}\n")
        else:
            output.append(f"- **{app_name}**\n")

    output.append(f"\n---\n\n*{len(built_files)} apps built*\n")

    with open("built_apps/README.md", "w", encoding="utf-8") as f:
        f.writelines(output)

    print(f"Generated built_apps/README.md with {len(built_files)} apps")
    sys.exit(0)


if __name__ == "__main__":
    main()
