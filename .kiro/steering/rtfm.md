---
inclusion: manual
description: "API verification workflow — read docs before writing API code"
---
# RTFM - Read The Fantastic Manual

**CRITICAL: API Verification Workflow (MANDATORY)**

**BEFORE writing ANY code that uses an API path:**

1. **STOP** - Do NOT assume fields exist
2. **SEARCH docs FIRST**: `grep -r "keyword" docs/ncos-api/ --include="*.md"`
3. **READ relevant docs** - Understand proper usage patterns and examples
4. **CHECK DTD**: `curl -s -u admin:pass http://router/api/dtd/config/path | python3 -m json.tool`
5. **TEST with curl**: `curl -s -u admin:pass http://router/api/status/path | python3 -m json.tool`
6. **VERIFY fields** - Only use fields that actually exist in the response
7. **THEN code** - Write code based on verified, documented structure

**CRITICAL: ALWAYS use REST API with basic auth (curl -u admin:pass), NEVER use SSH for API validation**

**If you skip these steps, you WILL create broken code.**

**NEVER EVER:**
- Assume a field exists without testing
- Make up API structures based on what "should" be there
- Prioritize speed over correctness
- Write code first and test later
- Use SSH for API validation - always use REST with basic auth
- Test APIs before reading documentation

**Key docs to search:**
- `docs/ncos-api/README.md` - Quick reference for all APIs
- `docs/ncos-api/status/` - Status API examples
- `docs/ncos-api/config/PATHS.md` - All config paths
- `docs/ncos-api/client-usage-qos.md` - QoS and client usage patterns
- `cp.py` - Helper functions reference

**Always check cp.py for helper functions before using direct API calls**
