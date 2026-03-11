# Automatic Reflection System

## MANDATORY WORKFLOW - NO EXCEPTIONS

**STOP. Before responding "task complete" or ending ANY response where you:**
- Deployed code
- Fixed an error
- Answered a technical question
- Made any API call

**YOU MUST:**

1. **Ask yourself**: Did I make ANY mistake, assumption, or learn something new?
2. **If YES**: Update the relevant rule/doc file BEFORE responding
3. **If NO**: Proceed with response

---

## Quick Reflection (30 seconds)

**Did I:**
- ❌ Code first, then fix? → Update rules with correct pattern
- ❌ Assume API structure without checking? → Update api-reference.md
- ❌ Get an error? → Add guardrail to prevent it
- ❌ Find docs were wrong? → Fix them
- ✅ Follow rules perfectly with no issues? → No update needed

**If ANY ❌, update files NOW before responding.**

---

## What to Document

**DO document:**
- API structures and field locations (e.g., `device['info']['type']` not `device['type']`)
- Common mistakes and how to avoid them (e.g., "always check DTD first")
- Workflow improvements (e.g., "curl before coding")
- Patterns that apply to multiple apps (e.g., "all modem diagnostics are nested")

**DON'T document:**
- App-specific logic
- One-off solutions that won't apply elsewhere
- Implementation details of a single app
- Anything that only matters for one specific use case

**Test: Would this help me build a DIFFERENT app correctly? If no, don't document it.**

---

## Response Format

**After update (if needed):**
- Minor fix: "✓ Done. Updated [file] with [what]."
- Critical fix: "⚠️ Done. Found critical issue: [what]. Updated [file]."
- No update: "✓ Done."

---

## Why This Matters

Every mistake you make and don't document, you'll make again. Every time you fix something, capture it so you don't repeat the error.

**This is not optional. This is the workflow.**