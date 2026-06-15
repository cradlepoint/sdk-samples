#!/usr/bin/env python3
"""Generate catalog.json for the NCOS SDK App Store from all package.ini files."""
import os
import json
import configparser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = REPO_ROOT / 'apps'

# Download URLs - same-origin Pages path (avoids CORS)
DOWNLOAD_BASE = 'apps'


def parse_package_ini(ini_path):
    """Parse a package.ini and return app metadata dict."""
    config = configparser.ConfigParser()
    config.read(ini_path)

    for section in config.sections():
        app = {
            'name': section,
            'vendor': config[section].get('vendor', 'Ericsson'),
            'developer': config[section].get('developer', 'Community'),
            'notes': config[section].get('notes', ''),
            'tags': config[section].get('tags', ''),
            'version_major': config[section].get('version_major', '0'),
            'version_minor': config[section].get('version_minor', '0'),
            'version_patch': config[section].get('version_patch', '0'),
            'firmware_major': config[section].get('firmware_major', '7'),
            'firmware_minor': config[section].get('firmware_minor', '26'),
            'auto_start': config[section].getboolean('auto_start', fallback=False),
            'restart': config[section].getboolean('restart', fallback=False),
            'reboot': config[section].getboolean('reboot', fallback=False),
        }
        app['version'] = f"{app['version_major']}.{app['version_minor']}.{app['version_patch']}"
        app['firmware'] = f"{app['firmware_major']}.{app['firmware_minor']}.x"

        # Parse tags into a list
        app['tags_list'] = [t.strip() for t in app['tags'].split(',') if t.strip()]

        # Determine developer label
        dev = app['developer'].lower()
        if dev == 'ericsson':
            app['developer_label'] = 'Ericsson'
        elif dev in ('partner', 'partners'):
            app['developer_label'] = 'Partners'
        else:
            app['developer_label'] = 'Community'

        # Download URL (same-origin, served from Pages)
        filename = f"{section} v{app['version']}.tar.gz"
        app['download_url'] = f"{DOWNLOAD_BASE}/{filename}"
        app['download_filename'] = filename

        return app
    return None


def find_readme(app_dir):
    """Find and read readme content for an app."""
    for name in ['readme.md', 'README.md', 'readme.txt', 'README.txt']:
        readme_path = app_dir / name
        if readme_path.exists():
            try:
                return readme_path.read_text(encoding='utf-8', errors='replace')
            except Exception:
                return ''
    return ''


def scan_apps(base_dir, archived=False):
    """Scan a directory tree for apps (dirs containing package.ini)."""
    apps = []
    for dirpath, dirnames, filenames in os.walk(base_dir):
        dirnames[:] = [d for d in dirnames if d not in
                       ['.git', '.github', '.kiro', 'METADATA', '__pycache__', '.venv', 'templates', 'archive']]
        if 'package.ini' in filenames:
            app_dir = Path(dirpath)
            ini_path = app_dir / 'package.ini'
            app = parse_package_ini(ini_path)
            if app:
                app['archived'] = archived
                app['path'] = str(app_dir.relative_to(REPO_ROOT))
                app['readme'] = find_readme(app_dir)
                apps.append(app)
            # Don't descend into app subdirectories
            dirnames.clear()
    return apps


def main():
    catalog = []

    # Scan main apps (excludes templates/ and archive/ automatically)
    if APPS_DIR.exists():
        catalog.extend(scan_apps(APPS_DIR, archived=False))

    # Sort by name
    catalog.sort(key=lambda a: a['name'].lower())

    # Collect all unique tags across apps
    all_tags = set()
    for app in catalog:
        all_tags.update(app['tags_list'])
    tags = sorted(all_tags)

    output = {
        'tags': tags,
        'apps': catalog,
        'total': len(catalog),
    }

    out_path = Path(__file__).parent / 'catalog.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"Generated catalog.json with {len(catalog)} apps and {len(tags)} unique tags")


if __name__ == '__main__':
    main()
