---
name: customer-data-cleaner
description: Cleans messy customer CSV files — detects encoding and delimiter, maps headers to standard names, trims junk values, normalizes names, emails, phones (E.164), dates (ISO), countries (ISO codes) and postal codes, merges duplicate customers, and reports every unfixable value. Use when asked to clean, tidy, standardize, deduplicate, or fix a customer, contact, client, or lead list in CSV form.
argument-hint: path/to/customers.csv
---

# Customer Data Cleaner

Run `scripts/clean_customer_data.py` (standard library only). It never modifies the input file.

## Workflow

1. **Profile first** with a dry run. It prints the JSON report and writes nothing:
   ```
   py .claude/skills/customer-data-cleaner/scripts/clean_customer_data.py data.csv --dry-run
   ```
2. **Check the report** before cleaning:
   - `header_mapping` / `unmapped_columns`: if a column was mapped wrongly or should be mapped, fix it with `--map "Original Header=email"` (repeatable).
   - `date_orders`: if any `how` says `ambiguous` or `conflicting`, ask the user whether dates are day-first or month-first and pass `--date-order dmy|mdy|ymd`.
   - Phones without a country code and no country column: ask the user for the dialing code and pass `--default-country-code 351`.
   - `duplicate_groups_sample`: confirm that the matches are real. Change the keys with `--dedupe-keys email`, or turn deduplication off with `--no-dedupe`.
3. **Clean** with the chosen flags (outputs go to `.tmp/` by default; change with `--out-dir`):
   ```
   py .claude/skills/customer-data-cleaner/scripts/clean_customer_data.py data.csv --default-country-code 351
   ```
4. **Report to the user**: rows in/out, duplicates merged, main changes, and the issue count, plus the paths to the outputs:
   - `.tmp/csv/<name>_clean.csv`: cleaned data (UTF-8 with BOM so Excel opens it correctly)
   - `.tmp/csv/<name>_issues.csv`: values the script could not fix, by source row and column
   - `.tmp/json/<name>_report.json`: full report
5. If the user wants to fix the issues, edit them in `_clean.csv`. Look rows up by `customer_id` or email, since source row numbers refer to the input file.

## What gets fixed

Full rules are in [references/cleaning_rules.md](references/cleaning_rules.md). In short:

| Field | Result |
|---|---|
| All values | trimmed, whitespace collapsed, null tokens (`N/A`, `null`, `-`, …) → empty |
| Names, city | ALL CAPS / all lower → Title Case (keeps `da`, `dos`, `O'Neill`, `McDonald`); `Smith, John` → `John Smith` |
| Email | lowercased, common domain typos fixed (`gmial.com`); invalid ones flagged |
| Phone | E.164 (`+351912345678`) using the row's country, else `--default-country-code`; extensions dropped |
| Dates | ISO `YYYY-MM-DD`; day/month order inferred per column |
| Country | ISO alpha-2 (`Portugal`, `PRT` → `PT`) |
| Rows | fully empty rows dropped; duplicates merged (first row wins, blanks filled from the others) |

Unfixable values stay as they were in the output and are listed in the issues file, so no data is lost silently.

## Extending

Add header aliases to `ALIASES`, countries to `COUNTRIES` + `DIALING_CODES`, or email typos to `EMAIL_DOMAIN_TYPOS` at the top of the script. Test the change with `assets/sample_messy_customers.csv` (cp1252, semicolon-delimited, includes duplicates and bad rows).

## Learnings

- `csv.Sniffer` picked `,` for a `;`-delimited file because a quoted-looking `Smith, John` sat in the sample. The script now counts candidate delimiters in the header line instead.
- A single `--default-country-code` prefixed `+351` to a US number. The script now uses the row's country first and falls back to the flag.
- Python's `csv` module handles quoted multi-line fields. Embedded newlines are collapsed to spaces.
- Rows with the wrong field count are padded or truncated to fit the header and logged as issues (column `*`). They usually mean an unquoted delimiter inside a value, so review them by hand.
- Stripping the trunk `0` when adding a country code is wrong for Italian landlines (the `0` is kept after `+39`). Pass `--default-country-code` carefully for IT data.
- The Edit/Write tools can turn `﻿`/` ` escapes into literal invisible characters. Keep them as escapes in the source (check with `grep -n 'ufeff\|u00a0'`).
