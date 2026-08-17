# Claude Code laptop migration — restore on new laptop

Companion doc to the export built on 2026-08-17:
`claude-code-user-export-2026-08-17.zip` (plugins, MCP servers, skills, agents,
rules, settings — user scope, not project scope). This machine's install method was
`native` (binary at `~/.local/bin/claude.exe`), so the new laptop should use the
same install path.

## 1. Install Claude Code

Open PowerShell (not Git Bash, not cmd) on the new laptop:

```powershell
irm https://claude.ai/install.ps1 | iex
```

Then run `claude` once — this logs you in and creates a fresh `~/.claude/` and
`~/.claude.json`. Do this **before** copying anything over, so those files exist to
merge into.

## 2. Get the zip there and extract it

However you move it (USB / OneDrive / email to yourself), then on the new laptop:

```powershell
Expand-Archive -Path "$env:USERPROFILE\Desktop\claude-code-user-export-2026-08-17.zip" -DestinationPath "$env:USERPROFILE\Desktop\cc-import"
```

## 3. Copy the plain-file pieces straight over

```powershell
$src = "$env:USERPROFILE\Desktop\cc-import"
Copy-Item "$src\skills\*" "$env:USERPROFILE\.claude\skills\" -Recurse -Force
Copy-Item "$src\plugins\local-marketplace" "$env:USERPROFILE\.claude\local-marketplace" -Recurse -Force
Copy-Item "$src\agents\*" "$env:USERPROFILE\.claude\agents\" -Recurse -Force      # optional
Copy-Item "$src\rules\*" "$env:USERPROFILE\.claude\rules\" -Recurse -Force        # optional
Copy-Item "$src\keybindings.json" "$env:USERPROFILE\.claude\keybindings.json" -Force
```

`plugins\local-marketplace` is the irreplaceable one — it holds the 3 custom
plugins (`vultr-ssh`, `windows-server-deploy`, `myway-cloudflare`) that have no
remote repo backing them.

## 4. Before merging the MCP block — decide on the 3 broken entries

Open `cc-import\mcp-servers.json` and either:

- **Fix the paths**: copy `C:\Users\piotrperesiak\MCP servers\KYC MCP\` and
  `C:\Projects\philips-hue\hue-mcp` over to the new laptop at the same paths, and
  confirm Python lands at `C:\Python312\python.exe` (or edit the
  `voicemode`/`kyc-mcp` `command` fields to match wherever Python actually is), or
- **Delete those 3 entries** (`voicemode`, `kyc-mcp`, `hue`) from the file if you
  don't need them on this machine.

Also decide whether you want the `n8n-mcp` / `n8n-mcp-community` entries — they
only work if n8n is reachable at `localhost:5678` with that same token on the new
laptop. Those entries carry live bearer tokens in plain text; treat the file like a
credentials export, not a config file.

## 5. Merge settings.json and mcp-servers.json — don't overwrite

A fresh `.claude.json`/`settings.json` on the new laptop already has its own
onboarding state, theme, and `projects` entries — overwrite wholesale and you lose
that. Merge just the relevant keys instead. Use `-AsHashtable` when reading these
JSON files in PowerShell: `ConvertFrom-Json`'s default object type is
case-insensitive and throws on Windows-path key collisions (e.g.
`C:/Projects/x` vs `C:/projects/x` in the `projects` map).

```powershell
# Merge settings.json (enabledPlugins, extraKnownMarketplaces, hooks, statusLine)
$new = Get-Content "$env:USERPROFILE\.claude\settings.json" -Raw | ConvertFrom-Json -AsHashtable
$old = Get-Content "$src\settings.json" -Raw | ConvertFrom-Json -AsHashtable
foreach ($key in @('enabledPlugins','extraKnownMarketplaces','hooks','statusLine')) {
    if ($old.ContainsKey($key)) { $new[$key] = $old[$key] }
}
$new | ConvertTo-Json -Depth 10 | Set-Content "$env:USERPROFILE\.claude\settings.json"

# Merge mcpServers into .claude.json
$newCfg = Get-Content "$env:USERPROFILE\.claude.json" -Raw | ConvertFrom-Json -AsHashtable
$mcp = Get-Content "$src\mcp-servers.json" -Raw | ConvertFrom-Json -AsHashtable
$newCfg['mcpServers'] = $mcp['mcpServers']
$newCfg | ConvertTo-Json -Depth 10 | Set-Content "$env:USERPROFILE\.claude.json"
```

## 6. Reinstall gstack (not copied in the export)

`gstack` isn't a plain skill — it's a full third-party CLI (bun/npm project cloned
from `github.com/garrytan/gstack`) that registers itself under
`~/.claude/skills/gstack` so its subcommands surface as skills. It was 1.35 GB,
mostly `node_modules` with native bindings, so it wasn't copied — reinstall it
fresh instead.

Requirements first: **Git**, **Bun** (`irm bun.sh/install.ps1 | iex`), **Node.js**
(Windows-only requirement per gstack's own docs). Then, in **Git Bash** (its
`./setup` is a shell script, won't run under plain PowerShell):

```bash
git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack && cd ~/.claude/skills/gstack && ./setup
```

## 7. Verify

```powershell
claude --version
claude mcp list
```

Then inside a `claude` session: check `/plugin` shows your enabled plugins, try one
of the local-marketplace skills (`/vultr-ssh` or similar), and confirm
`/office-hours` or another gstack skill responds — that confirms gstack's own setup
wired itself back into `~/.claude/skills/`.

## What was intentionally left out of the export

- `.credentials.json` — don't copy auth tokens between machines, log in fresh
  instead.
- `~/.claude/plugins/cache/` — git clones of marketplace repos, re-downloaded
  automatically once `enabledPlugins`/`extraKnownMarketplaces` are in place.
- The rest of `~/.claude.json` — session history, 64 projects' worth of
  machine-local paths, `machineID`, `anonymousId`.
