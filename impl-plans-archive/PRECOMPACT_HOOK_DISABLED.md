# PreCompact Hook — Disabled 2026-05-13

## Why it was disabled

`hook_precompact` in `mempalace/hooks_cli.py` unconditionally outputs `{"decision": "block"}` on
every `/compact` attempt — there is no "already saved" state it checks, no env var bypass, no
configuration toggle. It blocks forever regardless of what was saved to MemPalace.

## What was changed

**File:** `C:\Users\piotrperesiak\.claude\plugins\cache\mempalace\mempalace\3.3.5\hooks\hooks.json`

The `PreCompact` key was renamed to `_PreCompact_disabled` so the hook is ignored by Claude Code
but the original command is preserved for easy restoration.

**Current state (disabled):**
```json
{
  "description": "MemPalace auto-save and pre-compact hooks",
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/mempal-stop-hook.sh\""
          }
        ]
      }
    ],
    "_PreCompact_disabled": []
  }
}
```

## To restore the hook

Edit `hooks.json` and rename `_PreCompact_disabled` back to `PreCompact`:

```json
{
  "description": "MemPalace auto-save and pre-compact hooks",
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/mempal-stop-hook.sh\""
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/mempal-precompact-hook.sh\""
          }
        ]
      }
    ]
  }
}
```

## Notes

- The `Stop` hook is **unaffected** — periodic auto-saves still fire normally.
- If mempalace is updated via plugin manager, `hooks.json` may be overwritten and the hook
  re-enabled automatically.
- The precompact hook script itself (`mempal-precompact-hook.sh`) is unchanged — only the
  registration in `hooks.json` was disabled.
