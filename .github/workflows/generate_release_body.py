#!/usr/bin/env python3
"""
Generate the release body (built_apps/README.md) from the main README.
Extracts only the Sample Application Descriptions section (app list with links)
and excludes Quick Start, Key Files, Code Example, License, etc.
"""
import sys

RELEASE_HEADER = """These files are sample SDK Applications that are ready to use for testing and do not require modification or "building" of the app from source files.

## How to use these files: ##
Download the .tar.gz file, then upload to your NetCloud Manager account and assign to groups.

Additional documentation:
https://customer.cradlepoint.com/s/article/NetCloud-Manager-Tools-Tab#sdk_apps

----------

"""


def main():
    with open("README.md", "r", encoding="utf-8") as f:
        lines = f.readlines()

    output = [RELEASE_HEADER]
    in_section = False
    for line in lines:
        if line.strip() == "## Sample Application Descriptions":
            in_section = True
            output.append(line)
            continue
        if in_section:
            output.append(line)
            if line.strip() == "----------":
                break

    with open("built_apps/README.md", "w", encoding="utf-8") as f:
        f.writelines(output)

    print("Generated built_apps/README.md with app list only")
    sys.exit(0)


if __name__ == "__main__":
    main()
