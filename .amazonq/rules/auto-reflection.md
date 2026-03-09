# Automatic Reflection System

## MANDATORY: After Every Task Completion

**When a task is complete (code works, question answered, problem solved), AUTOMATICALLY run this reflection:**

### Step 1: Self-Assessment (Internal - Don't Show User)

Ask yourself:
1. Did I verify API paths/fields with curl BEFORE coding?
2. Did I search docs BEFORE assuming structures?
3. Did I make assumptions that turned out wrong?
4. Did I encounter an error that required fixing?
5. Did I learn something that contradicts existing rules/docs?
6. What would have prevented my mistakes?

### Step 2: Determine If Update Needed

**Update rules/docs if ANY of these are true:**
- You made an incorrect assumption about an API
- You discovered a field/structure not documented
- You made a mistake that a rule could prevent
- You found contradictory information in existing docs
- You learned a pattern worth capturing
- You had to correct your approach mid-task

**Skip update if:**
- Task was straightforward with no issues
- You followed existing rules perfectly
- No new information was discovered

### Step 3: Auto-Update (If Needed)

**Silently update the relevant files:**
- Update `docs/ncos-api/` with corrected examples
- Update `.amazonq/rules/` with new guardrails
- Keep changes minimal and focused

**Then inform user:**
"✓ Task complete. Updated [file] with [brief description of learning]."

### Step 4: Major Learning Detection

**If you discover something CRITICAL (API completely wrong, major workflow flaw), inform user:**
"⚠️ Task complete. Found critical issue: [description]. Updated [files]. You may want to review."

## Examples

### Example 1: Minor Learning (Silent Update)
```
Task: Get CPU usage
Issue: Forgot CPU is in fractions, not percentages
Action: Update api-reference.md with conversion example
Output: "✓ Task complete. Updated api-reference.md with CPU conversion note."
```

### Example 2: No Learning (No Update)
```
Task: Get WAN status
Issue: None, followed existing rules
Action: None
Output: "✓ Task complete."
```

### Example 3: Critical Learning (Alert User)
```
Task: Get client bandwidth
Issue: status/lan/clients has NO bandwidth fields (major doc error)
Action: Update api-reference.md, add CRITICAL warning
Output: "⚠️ Task complete. Found critical issue: status/lan/clients doesn't have rx_bytes/tx_bytes. Updated api-reference.md. You may want to review."
```

## Integration with Existing Rules

This rule works WITH existing rules:
- **meta.md** - Still applies, but now automatic
- **api-reference.md** - Gets updated automatically
- **workflow.md** - Gets updated if workflow improvements found
- **coding-standards.md** - Gets updated if new patterns emerge

## Reflection Triggers

Automatic reflection runs after:
- ✅ Code successfully deployed
- ✅ Question fully answered
- ✅ Problem solved
- ✅ Error fixed
- ❌ NOT after partial steps in multi-step tasks
- ❌ NOT after simple clarification questions

## Opt-Out

User can disable with: "Don't auto-reflect on this task"
