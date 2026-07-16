# hello_world
The simplest possible SDK app. Logs "Hello World!" and exits. Intended as a starting template for new SDK app development.

## What It Does

The entire application is three lines of code:

```python
# hello_world - log "Hello World!"
import cp
cp.log('Hello World!')
```

It imports the `cp` module and logs a single message. That's it.

## Purpose

This app serves as:
- A minimal template for creating new SDK apps
- A quick test to verify the SDK development environment is working
- A reference for the bare minimum an SDK app needs

## Expected Output

In the router's SDK app log:

```
Hello World!
```

The app runs once and logs the message. With `restart = true` in package.ini, it will restart and log again repeatedly.

## Creating a New App from This Template

1. Copy the `hello_world` directory to a new folder with your app name
2. Rename `hello_world.py` to match your new app name
3. Update `package.ini`:
   - Change the section name `[hello_world]` to your app name
   - Generate a new `uuid`
   - Update `notes`, `version`, and `tags`
4. Replace the `cp.log('Hello World!')` line with your app logic

## Files

| File | Description |
|------|-------------|
| `hello_world.py` | The app code (3 lines) |
| `package.ini` | App metadata and configuration |
| `start.sh` | Shell script to launch the Python app |

## Requirements

- Router firmware 7.26 or later
- No additional dependencies beyond the `cp` module
