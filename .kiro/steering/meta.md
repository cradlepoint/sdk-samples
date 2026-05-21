---
inclusion: auto
description: "Documentation maintenance reference - what goes where"
---
# Documentation Maintenance

Reflection is enforced by the `reflect-on-learnings` agentStop hook. This file defines *how* to update docs when you learn something.

## Response Format

- Minor fix: "✓ Done. Updated [file] with [what]."
- Critical fix: "⚠️ Done. Found critical issue: [what]. Updated [file]."
- No update: "✓ No new learnings."

## When to Update

- An API returns different data than documented
- You find a common mistake or gotcha
- You learn a better pattern or workflow
- You correct wrong information

## What Goes Where

**Rules (.kiro/steering/)** - Quick reference, guardrails:
- Critical "don't do this" warnings
- Common gotchas and API quirks
- Workflow patterns
- Keep concise — point to docs for details

**Docs (docs/ncos-api/)** - Comprehensive reference:
- Full API examples with all fields
- Complex patterns and edge cases
- Complete code samples

## How to Update

1. Fix the immediate issue first
2. Update docs — correct examples, add missing fields
3. Update rules — add guardrails to prevent recurrence
4. Keep it minimal — only add what prevents future errors

## Only Document General Learnings

**DO update rules for:** API behavior, router constraints, SDK patterns, file system behavior, web dev on routers.

**DO NOT update rules for:** App-specific logic, business logic, feature-specific implementations, one-off UI decisions.
