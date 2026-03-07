# RTFM - Read The Fantastic Manual

**BEFORE writing ANY code that uses an API:**

1. **Check @cp.py** - See if a helper function already exists
2. **Search docs** - `grep -r "keyword" docs/ncos-api/ --include="*.md"`
3. **Read @docs/ncos-api/README.md** - Common patterns and examples
4. **Test with curl** - Verify API structure before coding
5. **Check rules** - Review `.amazonq/rules/` for gotchas and patterns

**Key docs:**
- `@docs/ncos-api/README.md` - Quick reference for all APIs
- `@docs/ncos-api/status/` - Status API examples
- `@docs/ncos-api/config/PATHS.md` - All config paths
- `@cp.py` - Helper functions reference

**Never:**
- Assume fields exist without testing
- Make up API structures
- Skip verification steps
