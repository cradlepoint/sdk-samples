#!/usr/bin/env bash
# Cross-platform venv setup for NCOS SDK development
set -e

VENV_DIR=".venv"

# Detect Python command
if command -v python3 &> /dev/null; then
    PY=python3
elif command -v python &> /dev/null; then
    PY=python
else
    echo "ERROR: Python 3 not found. Install Python 3.7+ from https://www.python.org/downloads/"
    exit 1
fi

# Verify Python version >= 3.7
VERSION=$($PY -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MAJOR=$($PY -c "import sys; print(sys.version_info.major)")
MINOR=$($PY -c "import sys; print(sys.version_info.minor)")

if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 7 ]; }; then
    echo "ERROR: Python 3.7+ required, found $VERSION"
    exit 1
fi

echo "Using $PY ($VERSION)"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    $PY -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists in $VENV_DIR"
fi

# Activate and install
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    source "$VENV_DIR/Scripts/activate"
else
    source "$VENV_DIR/bin/activate"
fi

echo "Upgrading pip..."
pip install -U pip

echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "Setup complete! Virtual environment is at $VENV_DIR"
echo "Activate it with:"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    echo "  $VENV_DIR\\Scripts\\activate"
else
    echo "  source $VENV_DIR/bin/activate"
fi
