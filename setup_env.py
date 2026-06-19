#!/usr/bin/env python3
"""Set up the development environment.

Creates a .venv virtual environment and installs dependencies from
requirements.txt. Works on Windows, macOS, and Linux.

Usage:
    python setup_env.py
    python3 setup_env.py
"""

import os
import subprocess
import sys


def main():
    venv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.venv')
    py = sys.executable

    # Create virtual environment
    if not os.path.isdir(venv_dir):
        print('Creating virtual environment in .venv...')
        subprocess.run([py, '-m', 'venv', venv_dir], check=True)
    else:
        print('Virtual environment already exists in .venv')

    # Determine paths inside venv
    if sys.platform == 'win32':
        pip = os.path.join(venv_dir, 'Scripts', 'pip')
        venv_py = os.path.join(venv_dir, 'Scripts', 'python')
    else:
        pip = os.path.join(venv_dir, 'bin', 'pip')
        venv_py = os.path.join(venv_dir, 'bin', 'python')

    # Upgrade pip
    print('Upgrading pip...')
    subprocess.run([venv_py, '-m', 'pip', 'install', '-U', 'pip'], check=True)

    # Install requirements
    req = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'requirements.txt')
    if os.path.isfile(req):
        print('Installing dependencies from requirements.txt...')
        subprocess.run([pip, 'install', '-r', req], check=True)
    else:
        print('No requirements.txt found, skipping dependency install.')

    # Activation instructions
    print('\nSetup complete!')
    if sys.platform == 'win32':
        print('Activate the environment with:  .venv\\Scripts\\activate')
    else:
        print('Activate the environment with:  source .venv/bin/activate')


if __name__ == '__main__':
    main()
