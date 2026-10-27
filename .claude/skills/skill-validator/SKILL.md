---
name: skill-validator
description: Validates SKILL.md files in .claude/skills/ against the project's skill authoring rules (name format, description length and voice, allowed frontmatter fields, line limit, Learnings section, forbidden auxiliary docs). Use after creating or editing any skill, or when asked to check, lint, or audit skills.
---

# Skill Validator

Run after creating or editing a skill:

```
py .claude/skills/skill-validator/scripts/validate_skills.py
```

Validate a single skill by passing its folder name:

```
py .claude/skills/skill-validator/scripts/validate_skills.py web-scraper
```

## Output

- `ERROR` lines break a hard rule. Fix them before considering the skill done.
- `WARN` lines come from heuristics (verb-like names, non-third-person descriptions). Check them; they can be false positives.
- Exit code is 1 when any error is found, 0 otherwise.

## Checks

| Check | Level |
|---|---|
| Frontmatter present, `name` and `description` set | ERROR |
| `name`: ≤64 chars, `[a-z0-9-]`, no "anthropic"/"claude" | ERROR |
| `name` matches folder name | ERROR |
| `name` looks verb-based (`create-pdf`, `scraping-web`) | WARN |
| `description`: ≤1024 chars, no XML tags | ERROR |
| `description` starts with imperative verb ("Generate") | WARN |
| Only allowed frontmatter fields | ERROR |
| SKILL.md ≤500 lines | ERROR |
| `## Learnings` section present | WARN |
| No README.md / CHANGELOG.md in skill folder | ERROR |

## Learnings

- `py` and `git` are installed under `%LOCALAPPDATA%\Programs\` but may not be on PATH. Fall back to `%LOCALAPPDATA%\Programs\Python\Launcher\py.exe` if `py` is not found.
- Windows PowerShell 5.1 writes UTF-8 files with a BOM; SKILL.md is read as `utf-8-sig` so the BOM does not hide the frontmatter.
- The script parses frontmatter without PyYAML so it runs with no dependencies; it handles only flat `key: value` pairs.
