# Phase 7: Security Hardening - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Startup-time security validation and environment-based log level control. Flask never boots with a default or missing SECRET_KEY. Log verbosity is driven by a DEBUG env var — OCR/PDF debug noise is suppressed in production.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase.

Key constraints from REQUIREMENTS.md (FIX-04, FIX-05):
- SECRET_KEY validation must happen at app startup (before first request), not at import time
- Log level must be INFO in production by default; DEBUG when DEBUG=true env var is set
- Existing logging calls must not be removed — only the root logger level changes

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Flask app factory pattern (app.py or __init__.py — read before planning)
- Existing logging setup (search for `logging.basicConfig` or `app.logger`)
- Environment variable loading (dotenv or os.environ pattern)

### Established Patterns
- From v3.0: AppError exception hierarchy in exceptions.py — startup error should use or extend this
- From Phase 6: logging.exception() preferred over print() for error capture
- Config via environment variables (SECRET_KEY, DEBUG already used by Flask)

### Integration Points
- App factory / create_app() function — startup validation hooks here
- Log level set once at app initialization, affects all module loggers

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Infrastructure phase.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
