"""Validate SKILL.md files against the authoring rules in CLAUDE.md.

Usage: py validate_skills.py [skill-folder-name ...]
"""

import re
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[2]

ALLOWED_FIELDS = {"name", "description", "argument-hint", "disable-model-invocation", "user-invocable"}
RESERVED_WORDS = ("anthropic", "claude")
FORBIDDEN_FILES = ("README.md", "CHANGELOG.md")
MAX_NAME, MAX_DESCRIPTION, MAX_LINES = 64, 1024, 500

VERBS = {
    "add", "analyze", "build", "check", "convert", "create", "delete", "draft", "edit",
    "extract", "fetch", "fix", "format", "generate", "get", "make", "manage", "parse",
    "post", "process", "publish", "read", "remove", "run", "scrape", "search", "send",
    "summarize", "sync", "translate", "update", "upload", "validate", "write",
}


def parse_frontmatter(text):
    """Return (fields, error) for flat `key: value` YAML frontmatter."""
    if not text.startswith("---"):
        return None, "missing YAML frontmatter (file must start with ---)"
    end = text.find("\n---", 3)
    if end == -1:
        return None, "frontmatter is not closed with ---"
    fields = {}
    for line in text[3:end].splitlines():
        if not line.strip() or line.startswith((" ", "\t", "#")):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            return None, f"unparseable frontmatter line: {line!r}"
        fields[key.strip()] = value.strip().strip("\"'")
    return fields, None


def validate(skill_dir):
    errors, warnings = [], []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return ["SKILL.md not found"], warnings

    try:
        text = skill_md.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"cannot read SKILL.md: {exc}"], warnings

    fields, error = parse_frontmatter(text)
    if error:
        return [error], warnings

    name = fields.get("name", "")
    if not name:
        errors.append("`name` is required")
    else:
        if len(name) > MAX_NAME:
            errors.append(f"`name` is {len(name)} chars (max {MAX_NAME})")
        if not re.fullmatch(r"[a-z0-9-]+", name):
            errors.append("`name` may only contain lowercase letters, numbers and hyphens")
        for word in RESERVED_WORDS:
            if word in name:
                errors.append(f"`name` contains reserved word {word!r}")
        if name != skill_dir.name:
            errors.append(f"`name` {name!r} does not match folder {skill_dir.name!r}")
        first = name.split("-")[0]
        if first in VERBS or first.endswith("ing"):
            warnings.append(f"`name` looks verb-based ({first!r}); use a noun form like 'pdf-generator'")

    description = fields.get("description", "")
    if not description:
        errors.append("`description` is required")
    else:
        if len(description) > MAX_DESCRIPTION:
            errors.append(f"`description` is {len(description)} chars (max {MAX_DESCRIPTION})")
        if re.search(r"<[A-Za-z/][^>]*>", description):
            errors.append("`description` must not contain XML tags")
        first = description.split()[0].lower().strip(".,")
        if first in VERBS:
            warnings.append(f"`description` starts with {first!r}; write in third person ('{first}s ...')")

    extra = set(fields) - ALLOWED_FIELDS
    if extra:
        errors.append(f"unsupported frontmatter fields: {', '.join(sorted(extra))}")

    line_count = len(text.splitlines())
    if line_count > MAX_LINES:
        errors.append(f"SKILL.md is {line_count} lines (max {MAX_LINES}); move detail to references/")

    if not re.search(r"^## Learnings\s*$", text, re.MULTILINE):
        warnings.append("no `## Learnings` section")

    for forbidden in FORBIDDEN_FILES:
        if (skill_dir / forbidden).exists():
            errors.append(f"{forbidden} is not allowed in a skill folder")

    return errors, warnings


def main(argv):
    if argv:
        dirs = [SKILLS_DIR / name for name in argv]
    else:
        dirs = sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir())
    if not dirs:
        print(f"No skills found in {SKILLS_DIR}")
        return 0

    total_errors = 0
    for skill_dir in dirs:
        if not skill_dir.is_dir():
            print(f"{skill_dir.name}: ERROR folder not found")
            total_errors += 1
            continue
        errors, warnings = validate(skill_dir)
        total_errors += len(errors)
        status = "FAIL" if errors else "OK"
        print(f"{skill_dir.name}: {status}")
        for msg in errors:
            print(f"  ERROR {msg}")
        for msg in warnings:
            print(f"  WARN  {msg}")

    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
