---
inclusion: always
---

# Dev Environment Check

The `check-venv` hook automatically runs `make.py setup` if `.venv` is missing at the start of every prompt. No manual intervention needed.

If setup fails, let the user know they can also run the **Setup Dev Environment** hook manually from the Kiro sidebar.
