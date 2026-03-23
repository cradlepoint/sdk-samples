---
inclusion: always
---

# Dev Environment Check

If the user asks to build, deploy, or run an app and `.venv` does not exist in the workspace root, do NOT auto-run setup. Instead, let the user know:

> It looks like the Python environment hasn't been set up yet. Click the Kiro ghost icon in the sidebar and run the **Setup Dev Environment** hook, then try again.

Do not mention this if `.venv` already exists.
