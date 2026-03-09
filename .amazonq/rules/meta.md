# Documentation Maintenance

## When to Update Rules and Docs

**ALWAYS update rules and/or docs when:**
- You discover an API returns different data than documented
- You find a common mistake or gotcha that should be prevented
- You learn a better pattern or workflow
- You correct wrong information
- You add helpful context that would prevent future errors

## What Goes Where

**Rules (.amazonq/rules/)** - Quick reference, guardrails:
- Critical "don't do this" warnings
- Common gotchas and mistakes
- Quick API structure reference
- Workflow patterns
- Keep concise - point to docs for details

**Docs (docs/ncos-api/)** - Comprehensive reference:
- Full API examples with all fields
- Complex patterns and edge cases
- Complete code samples
- Deep dives on specific topics

## How to Update

1. **Fix the immediate issue** - get the code working first
2. **Update docs** - correct examples, add missing fields, clarify structures
3. **Update rules** - add guardrails to prevent the mistake from happening again
4. **Keep it minimal** - only add what's necessary to prevent future errors

## MANDATORY: Automatic Reflection (See auto-reflection.md)

**After completing ANY task, automatic reflection runs:**
1. Self-assess: Did I make mistakes? Learn something new?
2. Determine: Does this warrant a rule/doc update?
3. Update: Silently fix docs/rules if needed
4. Inform: Tell user what was learned (if anything)

**This happens automatically - you don't need to be reminded.**

See `auto-reflection.md` for full details on the reflection process.

## Example

If you discover `cp.get('status/system')` returns `cpu` as fractions (0.05) not percentages (5):
- **Docs**: Add full example showing conversion: `cpu_percent = cpu.get('user', 0) * 100`
- **Rules**: Add quick note: `cpu: fractions (0.05 = 5%), NOT percentages`
