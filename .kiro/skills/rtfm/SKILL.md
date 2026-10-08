---
name: rtfm
description: Verify that an NCOS API path and its fields actually exist before writing code against them, by searching docs, checking the DTD, and testing the live endpoint with curl. Use when the user says "rtfm", asks you to verify or confirm an API path or field, or challenges an assumption you made about an API response. Accepts a path, e.g. /rtfm status/wan/devices.
---

# Verify an API path for real

If the user named one or more paths, verify those. Otherwise verify every API path in the code
you most recently wrote or proposed.

The six-step workflow is in `.kiro/steering/api-reference.md`, which is always in context — follow
it rather than restating it. This skill exists to make verification the task itself.

## Do it now, in order

1. `grep -r "keyword" docs/ncos-api/ --include="*.md"` — find the doc
2. Read it. Note the response shape and field names
3. Config paths: `curl -s -u admin:pass http://router/api/dtd/config/<path> | .venv/bin/python -m json.tool`
4. `curl -s -u admin:pass http://router/api/status/<path> | .venv/bin/python -m json.tool`
5. Compare every field your code touches against that real response

Router IP and credentials come from `sdk_settings.ini`. Never print the password. Always REST with
basic auth — never SSH for API validation.

## Then report concretely

State, per path:

- **Confirmed** — field seen in a live response or a documented example. Quote the value.
- **Documented only** — in `docs/ncos-api/` but not verified against this router.
- **Does not exist** — and what the real field is instead.

If a field you already used turns out to be wrong, fix the code in the same turn.

## Worth checking while you are in there

- A field that "makes sense" but is absent is the single most common failure. Absence is normal:
  feature-gated subtrees (`config/system/rtk`) and disabled services (`status/dhcpd`) return
  `null`, not an empty object.
- Which fields exist can depend on live state, not the model — modem signal keys change with the
  radio technology.
- A config PUT can return `ok` and apply nothing. Read the value back before trusting a write.

Full detail for these is in `docs/ncos-api/gotchas.md`. If you discover something new, use the
`learn` skill to record it.
