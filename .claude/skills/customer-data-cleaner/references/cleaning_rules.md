# Cleaning rules

Detailed behavior of `scripts/clean_customer_data.py`, in processing order.

## 1. Reading

- Encoding: tries `utf-8-sig`, then `cp1252`, then `latin-1` (latin-1 always decodes, so it is the last resort).
- Delimiter: whichever of `,` `;` `\t` `|` appears most in the header line.

## 2. Header mapping

Headers are slugified (`"E-Mail Address"` → `e_mail_address`) and then looked up in `ALIASES`.

| Canonical | Example aliases |
|---|---|
| customer_id | id, cust_id, client_id, account_id |
| first_name / last_name | fname, given_name, surname, apelido |
| full_name | name, customer_name, contact_name |
| email | e_mail, mail, email_address |
| phone | tel, mobile, cell, telefone, telemovel |
| company | organization, business, empresa |
| address, city, state | street, town, province, distrito, morada |
| postal_code | zip, postcode, codigo_postal |
| country | country_code, nation, pais |
| date_of_birth | dob, birthdate, data_nascimento |
| signup_date | created_at, join_date, customer_since |

Unknown columns keep their slugified name and stay in the output after the canonical ones. If two columns map to the same name, the later ones get suffixes (`phone_2`); they are cleaned with the same rules.

## 3. Value rules

**Null tokens** (case-insensitive, become empty): `n/a`, `na`, `null`, `none`, `nil`, `nan`, `-`, `--`, `?`, `unknown`, `not available`, `no email`, `#n/a`, `undefined`, `0000-00-00`.

**Names** (`first_name`, `last_name`, `full_name`, `city`): only re-cased when entirely upper or lower case. Particles (`da de do das dos e van von der den la le di du del`) stay lowercase unless they are the first word. Each part of a hyphen or apostrophe name is capitalized; `mc` prefixes become `Mc` + capital.

**Email**: lowercase, spaces removed, `,` → `.`, `mailto:` dropped, repeated dots collapsed, domain typos corrected. Validated against `local@domain.tld`.

**Phone**: extensions (`ext 22`, `x22`, `#22`) dropped. A leading `+` or `00` means international. Without one, the dialing code comes from the row's `country` (`DIALING_CODES`), else from `--default-country-code`, else the number is left as bare digits. A leading trunk `0` is removed when the code is added. Valid lengths are 7–15 digits.

**Dates** (`date_of_birth`, `signup_date`, any column with `date` in its name): numeric `a/b/c` with `/ . -` or space separators. A 4-digit first part is read as year-first. Otherwise the column's order is inferred: any first part > 12 means `dmy`, any second part > 12 means `mdy`. If both appear, the column is `conflicting`; if neither, it is `ambiguous`, and both fall back to `dmy`. Two-digit years up to the current year map to 20xx, otherwise 19xx. Named months are also handled (`5 March 2024`, `Mar 5, 2024`). Impossible dates (`31/02`) are flagged.

**Country**: mapped to ISO alpha-2 via `COUNTRIES` (English, Portuguese and native names, alpha-3 codes). Unknown values are flagged and kept.

**Postal code**: uppercased; spaces around `-` removed (`1000 - 001` → `1000-001`).

## 4. Rows

- Rows with every value empty after cleaning are dropped.
- Rows with too many or too few fields are padded or truncated and logged with column `*`.
- Duplicates: rows are grouped transitively when they are identical, or share any non-empty `--dedupe-keys` value (case-insensitive). Within a group the earliest row is kept and its empty fields are filled from the later rows.
