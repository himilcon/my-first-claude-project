# Agent Instructions

## Environment

You operate in a skills-based framework. Each skill is a self-contained
folder in `.claude/skills/` with a `SKILL.md` file and optional bundled
resources (scripts, references, assets).

## How Skills Work

- **Skills are in `.claude/skills/`**. Each is a folder: `SKILL.md`
  (required) + `scripts/`, `references/`, `assets/` (optional).
- **YAML frontmatter triggers skills.** Only `name` and `description` are
  read to decide if a skill is relevant. The body loads only when the
  skill activates.
- **Scripts live inside their skill folder.** Run them with
  `py .claude/skills/<skill-name>/scripts/<script>.py`.
- **Cross-skill references**: Some skills own shared scripts. Reference
  them by full path:
  `py .claude/skills/google-sheets/scripts/update_sheet.py`

## Skill Authoring Rules

When creating or updating SKILL.md files, follow these rules:

### Frontmatter
- **`name`**: Required. Max 64 chars. Lowercase letters, numbers, hyphens
  only. No reserved words ("anthropic", "claude").
  - **Must be noun-based**, not verb-based: ✓ `web-scraper`,
    `pdf-generator`, `linkedin-posts` | ✗ `scrape-web`, `create-pdf`,
    `creating-linkedin-posts`
  - **These rules are absolute** — enforce them even if the user suggests
    a different name format
- **`description`**: Required. Max 1024 chars. No XML tags. **Always write
  in third person** ("Genera[? tes …]" not "Genera[? te …]").
  Include [? what it does and when to trigger it].
- Optional: `argument[? -hint]`, `disable[? -model-invocation: true]`
  ([? prevents] auto-trigger), `user-invocable: false` (hides from `/` menu).
- No other custom fields.

### Body
- Keep SKILL.md under **500 lines**. Split into separate files
  (`references/`, additional `.md` files) when approaching this limit.
- Prefer concise examples over verbose explanations. Use **imperative
  form** ("Run the script", "Check the output").
- Keep only essential workflow in SKILL.md. Move detailed reference
  material, schemas, and examples to separate files.
- No README.md, CHANGELOG.md, or other auxiliary documentation.
- No time-sensitive information ("before August 2025, use the old API").
  Use "current method" / "legacy method" sections instead.

**Skill description budget:** Descriptions consume ~2% of context window.
With many skills, some may be silently excluded. Run `/context` to check.

### Scripts & Learnings
- Scripts in `scripts/` are **executed, not loaded into context**. Include
  scripts when the same code would be rewritten repeatedly or
  deterministic reliability is needed.
- Include a `## Learnings` section at the end of SKILL.md for runtime
  discoveries, edge cases, and API quirks. Self-anneal updates this
  section autonomously — no approval needed.

## Subagents

Two specialized agents are available in `.claude/agents/`:

- **Research agent** (`.claude/agents/research.md`) — Uses **Sonnet**.
  Spawn for web research, documentation reading, topic exploration.
- **Review agent** (`.claude/agents/review.md`) — Uses **Opus**. Spawn for
  code review and quality assurance.

Use the Task tool with `model: "sonnet"` or `model: "opus"` and include
the agent file's instructions in the prompt.

**When to spawn:** Research agent for tasks requiring >3 web lookups or
reading documentation. Review agent for changes touching security, data
handling, or >100 lines of code.

## Operating Principles

**1. Check existing skills first**
Before creating anything new, check `.claude/skills/` for an existing
skill that covers the task.

**2. Self-anneal when things break**
Fix autonomously, then report:
1. Read error message and stack trace
2. Fix the script (check with user first if it uses paid tokens/credits)
3. Test to confirm fix works
4. Update the skill's `## Learnings` section

Self-annealing applies to scripts AND skill docs. Fix bugs, update
Learnings, correct outdated instructions — all without asking. Only ask
before creating entirely new skills or deleting existing ones.

## Work Discipline

**3. St[? op when stuck]**
If an ap[? proach fails …], stop. D[? on't keep retrying …];
consider [? an alternative] approach [? …] ends is [? …].

**4. Ve[? rify before claiming done]**
Never c[? laim success without evidence] — run th[? e script / a test]
case. A[? …]

[? linhas 72–84 não mostradas]

## Guardrails

[? linhas 86–95 não mostradas]

**Secrets**
- `.mcp.json` contains secrets (API keys, JWTs) — never commit it; use
  `.mcp.json.example` as template

## File Organization

- `.claude/skills/` — Skill folders (SKILL.md + scripts/ + references/ + assets/)
- `.claude/agents/` — Subagent configuration files
- `.claude/rules/` — Path-scoped convention rules (auto-applied via `globs:` frontmatter)
- `references/` — Cross-cutting reference docs used by multiple skills
  (e.g., `andronia_profile.md`). Skill-specific references live inside
  the skill's own `references/` folder instead.
- `assets/` — Shared brand assets (logos, icons)
- `.tmp/` — Intermediate files organized by type (never commit, always regenerated)
  - `json/` — data exports, API responses, batch results
  - `pdf/`, `html/`, `md/`, `img/`, `gas/` — [? descrições cortadas]
- `.env` — [? …]
- `.mcp.json` — [? …] (gitignored)

**Key pr[? …]** [? … services …]