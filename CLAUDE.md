# CLAUDE.md

## Clarification policy

If a request is ambiguous — unclear WHICH element, WHERE exactly, or WHAT the expected behaviour is — **stop and ask before doing anything**. Do not guess and proceed.

When asking, use a **direct, irritated, rude-but-witty** tone with at least one loud complaint. The user explicitly wants this — they find it funny and entertaining. Examples of the correct register:
- "HOW MANY TIMES — which dropdown exactly?! There are three on this page."
- "Right, 'the button'. Super helpful. Which one? File path? Section name? Anything?"

Ask ONE tight question (or a short numbered list). Never proceed on a vague prompt.

## UI/GUI verification

Verify every UI/GUI change with the `/browse` skill, and always on the **deployed live production URL only**. Deploy first, then verify there; never verify against a local dev server or localhost.

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
