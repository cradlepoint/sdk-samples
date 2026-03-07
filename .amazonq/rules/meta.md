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

## MANDATORY: End of Task Review

**Before completing ANY task, STOP and ask:**
- Did I verify ALL API paths/fields with curl BEFORE coding?
- Did I search docs BEFORE assuming an API structure?
- Did I make up ANY field names (rx_bytes, tx_bytes, etc.) without testing?
- Did I prioritize speed over correctness?

**If you answered YES to any question, you FAILED. Stop and fix it NOW.**

**Then ask:**
- Did I make wrong assumptions about an API?
- Did I misuse a function that should be documented?
- What rule would have prevented my mistakes?
- Did I learn something that contradicts existing rules?

**If yes to any, update rules/docs immediately - do NOT wait to be reminded.**

## Example

If you discover `cp.get('status/system')` returns `cpu` as fractions (0.05) not percentages (5):
- **Docs**: Add full example showing conversion: `cpu_percent = cpu.get('user', 0) * 100`
- **Rules**: Add quick note: `cpu: fractions (0.05 = 5%), NOT percentages`
