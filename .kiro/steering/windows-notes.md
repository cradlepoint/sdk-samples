---
inclusion: manual
description: "Windows-only: the full Exit Code 1 explanation and the success-string table for each make.py operation"
---
# Windows Notes

Only relevant when the user's machine is Windows. Commands use `.venv\Scripts\python`.

## Exit Code 1 is expected — do NOT treat it as failure

On Windows this repo reports `Exit Code: 1` for **all** commands, not just `make.py`. It is a
terminal wrapper artifact. Never treat it as a failure signal.

1. **Never retry a command solely because of Exit Code: 1.** The command ran.
2. **Never ask the user for guidance** because of Exit Code: 1. Continue.
3. **Never loop** retrying the same command — if a command produced output, even partial, it executed.
4. **No output plus Exit Code: 1** — assume it succeeded and move on. Only investigate if a later
   step proves otherwise.
5. **Judge success only by printed output:**

   | Operation | Success looks like |
   |---|---|
   | Purge | `Purge successful` |
   | Build / package | `Package {app_name} v{x}.{y}.{z}.tar.gz created` |
   | Install | `Installing {archive} to {ip}...` (SCP drop after upload is normal) |
   | Deploy | the purge message appears (build + install follow, output may be swallowed) |
   | Status | `"state": "started"` in the JSON response |
   | Any Python script | the expected print output |

6. **Output may be partially swallowed** — the terminal sometimes shows only the first print of a
   multi-step operation. The remaining steps still executed.
7. **Character-by-character echo is cosmetic** — the terminal replays typed characters. Ignore the
   garbled repeated text before the real output.

If the output shows success messages but `Exit Code: 1`, the operation succeeded. Do not retry,
diagnose, or report failure. Move forward.
