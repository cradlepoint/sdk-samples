---
inclusion: always
---

# Dev Environment Setup Check

Before responding to the user's first request, check whether `.kiro/.setup_complete` exists in the workspace root.

If `.kiro/.setup_complete` does NOT exist:
1. Inform the user that the dev environment hasn't been set up yet and you're setting it up now.
2. Run `bash setup_env.sh` (macOS/Linux) or `setup_env.bat` (Windows) to create the venv and install dependencies.
3. After setup completes successfully, create the file `.kiro/.setup_complete` with the text "done" to prevent this check from running again.
4. Continue with the user's original request.

If `.kiro/.setup_complete` already exists, do nothing — skip this entirely and proceed with the user's request.
