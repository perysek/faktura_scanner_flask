# CLAUDE.md

## Clarification policy

If a request is ambiguous — unclear WHICH element, WHERE exactly, or WHAT the expected behaviour is — **stop and ask before doing anything**. Do not guess and proceed.

When asking, use a **direct, irritated, rude-but-witty** tone with at least one loud complaint. The user explicitly wants this — they find it funny and entertaining. Examples of the correct register:
- "HOW MANY TIMES — which dropdown exactly?! There are three on this page."
- "Right, 'the button'. Super helpful. Which one? File path? Section name? Anything?"

Ask ONE tight question (or a short numbered list). Never proceed on a vague prompt.

## gstack

Use the `/browse` skill from gstack for all web browsing. Never use `mcp__claude-in-chrome__*` tools.

### Available gstack skills

- `/office-hours` - Office hours
- `/plan-ceo-review` - Plan CEO review
- `/plan-eng-review` - Plan engineering review
- `/plan-design-review` - Plan design review
- `/design-consultation` - Design consultation
- `/design-shotgun` - Design shotgun
- `/design-html` - Design HTML
- `/review` - Code review
- `/ship` - Ship
- `/land-and-deploy` - Land and deploy
- `/canary` - Canary
- `/benchmark` - Benchmark
- `/browse` - Web browsing (use this for all web browsing)
- `/connect-chrome` - Connect Chrome
- `/qa` - QA
- `/qa-only` - QA only
- `/design-review` - Design review
- `/setup-browser-cookies` - Setup browser cookies
- `/setup-deploy` - Setup deploy
- `/retro` - Retro
- `/investigate` - Investigate
- `/document-release` - Document release
- `/codex` - Codex
- `/cso` - CSO
- `/autoplan` - Autoplan
- `/plan-devex-review` - Plan DevEx review
- `/devex-review` - DevEx review
- `/careful` - Careful mode
- `/freeze` - Freeze
- `/guard` - Guard
- `/unfreeze` - Unfreeze
- `/gstack-upgrade` - Upgrade gstack
- `/learn` - Learn

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health

## Design system (canonical)

One design language ("System B" / refined): **flat fills, 2–3px radii, CSS-variable
tokens, Inter, glyph icons over icon-fonts**. Full token reference:
`plans/260610-ui-usability-fixes/DESIGN-TOKENS.md`.

Rules:
- Tokens live in `static/css/input.css :root` (`--color-*`, `--radius-sm/md`).
  Never reintroduce `rounded-xl`/`rounded-2xl`/`bg-gradient-to-*`/raw `slate-*`
  buttons in authenticated templates.
- CSS build: edit `static/css/input.css`, run `npm run build:css`. **Never hand-edit
  `static/css/output.css`** (generated, gitignored, rebuilt on the server at deploy).
- Buttons: global `.refined-btn-primary/secondary` (flat) or `.form-btn-*`. Forms:
  `.form-input/.form-select/.form-textarea/.form-label/.form-card`.
- Sortable tables: `<th class="th-sortable" aria-sort="…">` wrapping a
  `.th-sort-btn` `<button>` + `.th-sort-icon` glyph (▲/▼). Sync `aria-sort` in the
  page's sort JS.
- Mobile: every page sets `{% block mobile_title %}Label{% endblock %}` (shown in
  the header < lg). Wide tables use the stacked-card pattern from DESIGN-TOKENS.md
  (`data-label` + ≤640px media block — see `clients/list.html`).
- Form controls must compute ≥16px font-size at ≤1023px (global guard in input.css
  — do not override with !important page styles).
