# Learn - Update Rules and Docs

**Review what you learned and update documentation:**

## Ask yourself:

- Did I discover an API returns different data than documented?
- Did I find a field that doesn't exist or works differently?
- Did I make wrong assumptions that should be prevented?
- Did I learn a better pattern or workflow?
- What rule would have prevented my mistakes?

## Explore APIs before documenting:

**Use `@explore_status.py` to verify API structures:**

```bash
# Explore a status path
python3 docs/ncos-api/explore_status.py status/wan/devices

# Use SSH method if REST fails
python3 docs/ncos-api/explore_status.py status/system --method ssh
```

This shows the ACTUAL API response with all fields - use it to verify structures before updating docs.

## Update locations:

**Rules (`.amazonq/rules/`)** - Add guardrails:
- Critical "don't do this" warnings
- Common gotchas and mistakes
- Quick API structure reference
- Workflow patterns

**Docs (`docs/ncos-api/`)** - Add examples:
- Correct API structures with all fields
- Complete working code samples
- Edge cases and limitations
- Deep dives on specific topics

## Remember:

- Update immediately - don't wait
- Keep rules concise - point to docs for details
- Add examples to docs - show don't tell
- Prevent future mistakes - make it impossible to fail
