#!/usr/bin/env python3
"""
Build script for the Tailscale Cradlepoint SDK app.
Matches the behaviour of the official Cradlepoint make.py:
  - Updates METADATA/MANIFEST.json (sorted keys, SHA-256 file hashes)
  - Regenerates METADATA/SIGNATURE.DS (raw SHA-256 bytes, no newline)
  - Packages files inside a 'tailscale/' subdirectory in the tar.gz

Usage: python build.py
Output: tailscale v<version>.tar.gz
"""

import configparser
import datetime
import gzip
import hashlib
import json
import os
import shutil
import tarfile

APP_NAME = "tailscale"
MANIFEST_PATH = os.path.join("METADATA", "MANIFEST.json")
SIGNATURE_PATH = os.path.join("METADATA", "SIGNATURE.DS")
IGNORE = {"__pycache__", ".DS_Store", "buildignore", "build.py", "SDK.pdf", "desktop.ini"}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_package_ini():
    config = configparser.ConfigParser()
    config.read("package.ini")
    return config[APP_NAME]


def update_manifest(pkg):
    hashed_files = {}
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in IGNORE and d != "METADATA"]
        for fname in files:
            if fname in IGNORE or fname.startswith("."):
                continue
            if fname.endswith(".tar.gz") or fname.endswith(".tar"):
                continue
            fpath = os.path.join(root, fname)
            # Use forward slashes, strip leading ./
            key = fpath.replace("\\", "/").lstrip("./")
            hashed_files[key] = sha256_file(fpath)

    manifest = {
        "app": {
            "auto_start": pkg.getboolean("auto_start"),
            "date": datetime.datetime.now().isoformat(),
            "files": hashed_files,
            "firmware_major": int(pkg.get("firmware_major", "0")),
            "firmware_minor": int(pkg.get("firmware_minor", "0")),
            "name": APP_NAME,
            "notes": pkg.get("notes", APP_NAME),
            "reboot": pkg.getboolean("reboot"),
            "restart": pkg.getboolean("restart"),
            "uuid": pkg.get("uuid", ""),
            "vendor": pkg.get("vendor", ""),
            "version_major": int(pkg.get("version_major", "0")),
            "version_minor": int(pkg.get("version_minor", "0")),
            "version_patch": int(pkg.get("version_patch", "0")),
        },
        "pmf": {
            "version_major": 1,
            "version_minor": 0,
            "version_patch": 0,
        },
    }

    os.makedirs("METADATA", exist_ok=True)
    manifest_bytes = json.dumps(manifest, indent=4, sort_keys=True).encode("utf-8")
    with open(MANIFEST_PATH, "wb") as f:
        f.write(manifest_bytes)

    print(f"Updated {MANIFEST_PATH}")
    return manifest_bytes


def update_signature(manifest_bytes):
    checksum = hashlib.sha256(manifest_bytes).hexdigest().encode("utf-8")
    with open(SIGNATURE_PATH, "wb") as f:
        f.write(checksum)
    print(f"Updated {SIGNATURE_PATH} -> {checksum.decode()}")


def build_tarball(pkg):
    version = "{}.{}.{}".format(
        pkg.get("version_major", "0"),
        pkg.get("version_minor", "0"),
        pkg.get("version_patch", "0"),
    )
    app_root = os.path.abspath(".")
    tar_name = f"{APP_NAME}.tar"
    gz_name = f"{APP_NAME} v{version}.tar.gz"

    with tarfile.open(tar_name, "w") as tar:
        tar.add(app_root, arcname=APP_NAME, filter=lambda t: _tar_filter(t, app_root))

    with open(tar_name, "rb") as f_in:
        with gzip.open(gz_name, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    os.remove(tar_name)
    print(f"Created {gz_name}")
    return gz_name


def _tar_filter(tarinfo, app_root):
    basename = os.path.basename(tarinfo.name)
    if basename in IGNORE:
        return None
    if basename.startswith("."):
        return None
    if basename.endswith(".tar.gz") or basename.endswith(".tar"):
        return None
    return tarinfo


if __name__ == "__main__":
    pkg = read_package_ini()
    manifest_bytes = update_manifest(pkg)
    update_signature(manifest_bytes)
    build_tarball(pkg)
