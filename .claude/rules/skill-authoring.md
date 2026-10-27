---
paths:
  - ".claude/skills/**"
globs: ".claude/skills/**"
---

# Skill authoring

When creating or editing anything under `.claude/skills/`:

- Follow the Skill Authoring Rules in `CLAUDE.md`.
- After saving, run `py .claude/skills/skill-validator/scripts/validate_skills.py <skill-name>` and fix every `ERROR` before reporting the skill as done.
- Record runtime discoveries in the skill's `## Learnings` section, not in CLAUDE.md.
