#!/usr/bin/env python3
"""
Generate config/PATHS.md from the NCOS DTD JSON.
Run from NCOS API Documentation/ or pass --dtd and --output paths.
"""
import json
import os
import argparse


def collect_paths(nodes, prefix="config"):
    """Recursively collect API paths from DTD nodes."""
    paths = []
    if not isinstance(nodes, dict):
        return paths
    for key, value in nodes.items():
        path = f"{prefix}/{key}" if prefix else key
        if isinstance(value, dict):
            child_nodes = value.get("nodes")
            if child_nodes is not None:
                paths.append(path)
                paths.extend(collect_paths(child_nodes, path))
            else:
                paths.append(path)
        else:
            paths.append(path)
    return paths


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_dtd = os.path.join(script_dir, "config", "dtd", "NCOS-DTD-7.25.101.json")
    default_out = os.path.join(script_dir, "config", "PATHS.md")

    parser = argparse.ArgumentParser(description="Generate config path index from DTD")
    parser.add_argument("--dtd", default=default_dtd, help="Path to DTD JSON")
    parser.add_argument("--output", default=default_out, help="Output PATHS.md path")
    args = parser.parse_args()

    with open(args.dtd, "r") as f:
        data = json.load(f)

    config = data.get("data", {}).get("config", {})
    nodes = config.get("nodes", {})
    if not nodes:
        nodes = config

    paths = collect_paths(nodes)
    paths.sort()

    lines = [
        "# config/ Path Index",
        "",
        "<!-- path: config -->",
        "<!-- generated from DTD - run generate_config_paths.py to update -->",
        "",
        "[config](README.md) / PATHS",
        "",
        "---",
        "",
        "Full list of config paths from the NCOS DTD schema. Use with `cp.get()`, `cp.put()`, or REST `/api/config/{path}`.",
        "",
        "## Paths",
        "",
    ]
    for p in paths:
        lines.append(f"- `{p}`")
    lines.append("")

    with open(args.output, "w") as f:
        f.write("\n".join(lines))

    print(f"Wrote {len(paths)} paths to {args.output}")


if __name__ == "__main__":
    main()
