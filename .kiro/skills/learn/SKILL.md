---
name: learn
description: Record something discovered during this session into the project's steering rules or NCOS API docs, after deciding whether it is general enough to be worth documenting and where it belongs. Use when the user says "learn", asks you to update the rules or docs with what you just found, or when you have corrected a wrong assumption about an API or the router.
---

# Record a learning

## 1. Decide if it is worth documenting

Did an API return something different from what was documented? Did a field not exist, or behave
differently? Did a wrong assumption cost time? Is there a better pattern? What rule would have
prevented the mistake?

**Document it (general):** API behavior and data structures · router environment constraints · SDK
patterns · file system behavior · network and connectivity patterns · web development on routers.

**Do not document it (app-specific):** one app's logic or algorithms · business logic · a single
feature's implementation · UI decisions for one app · app-specific data processing.

If it is app-specific, say so and stop. A rules file that accumulates one-app trivia stops being
readable, which is worse than not recording it.

## 2. Verify before writing it down

```bash
.venv/bin/python docs/ncos-api/explore_status.py status/wan/devices
```

This prints the real response with all fields. Confirm the structure first — a learning recorded
from a guess is worse than no learning.

Then check two things:

- **Is it already documented?** Search `docs/ncos-api/` and `.kiro/steering/` before adding.
- **Does it contradict something already written?** This is the most valuable kind of finding.
  Resolve it and correct the old entry. Never leave two conflicting claims in the repo — that
  costs more time later than the original gap did.

## 3. Put it in one place

**Rules — `.kiro/steering/`** — guardrails and quick reference. One line each, pointing to docs
for detail. Choose the owning topic file and only that file:

| Subject | File |
|---|---|
| API paths, `cp` module, gotcha index | `api-reference.md` |
| Python/cppython, libraries, memory, lifecycle | `coding-standards.md` |
| `make.py`, deploy, project layout | `workflow.md` |
| HTTP server, web template, HTML/CSS/JS | `web-standards.md` |
| GPS, NMEA, RTK | `gps-standards.md` |
| Speedtest engines, netperf | `speedtest-standards.md` |
| Containers | `container-standards.md` |

`core.md` changes only for a rule that is costly to get wrong in *every* session.

**Docs — `docs/ncos-api/`** — full examples, all fields, edge cases, complete code samples.

- Long-form verified gotchas → `docs/ncos-api/gotchas.md`, plus a one-line entry in the gotcha
  index in `api-reference.md`
- Path-specific findings → the matching file (`config/serial.md`, `status/rtk.md`, …)

## 4. Order of work

1. Fix the immediate issue first
2. Update the docs — correct the example, add the missing field
3. Add the one-line guardrail that prevents a recurrence
4. Keep it minimal, and do it now rather than later

## Response format

- Minor fix: "✓ Done. Updated [file] with [what]."
- Critical fix: "⚠️ Done. Found critical issue: [what]. Updated [file]."
- Nothing general learned: "✓ No new learnings."
