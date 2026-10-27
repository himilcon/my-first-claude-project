"""Clean a messy customer CSV.

Usage:
    py clean_customer_data.py INPUT.csv [--out-dir .tmp] [--dry-run]
        [--date-order auto|dmy|mdy|ymd] [--default-country-code 351]
        [--dedupe-keys email,phone] [--no-dedupe] [--map "Cust Mail=email"]

Writes (unless --dry-run):
    <out-dir>/csv/<stem>_clean.csv    cleaned rows, canonical headers first
    <out-dir>/csv/<stem>_issues.csv   one row per value that could not be fixed
    <out-dir>/json/<stem>_report.json summary of every change
Standard library only.
"""

import argparse
import csv
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")

NULL_TOKENS = {
    "", "n/a", "na", "null", "none", "nil", "nan", "-", "--", "?", "unknown",
    "not available", "no email", "noemail", "#n/a", "undefined", "0000-00-00",
}

# Header aliases (after slugifying) -> canonical column name.
ALIASES = {
    "first_name": ["first", "firstname", "fname", "given_name", "forename", "nome", "primeiro_nome"],
    "last_name": ["last", "lastname", "lname", "surname", "family_name", "apelido", "ultimo_nome"],
    "full_name": ["name", "fullname", "customer_name", "client_name", "contact_name", "nome_completo"],
    "email": ["e_mail", "email_address", "mail", "emailaddress", "customer_email", "correio_eletronico"],
    "phone": ["phone_number", "telephone", "tel", "mobile", "cell", "cellphone", "contact_number",
              "phone_no", "telefone", "telemovel"],
    "company": ["company_name", "organization", "organisation", "business", "empresa"],
    "address": ["street", "address_line_1", "address1", "street_address", "morada", "endereco"],
    "city": ["town", "cidade", "localidade"],
    "state": ["province", "region", "county", "distrito", "estado"],
    "postal_code": ["zip", "zipcode", "zip_code", "postcode", "post_code", "postalcode", "codigo_postal", "cp"],
    "country": ["country_name", "country_code", "nation", "pais"],
    "date_of_birth": ["dob", "birth_date", "birthdate", "birthday", "data_nascimento"],
    "signup_date": ["created", "created_at", "join_date", "joined", "registration_date", "date_joined",
                    "customer_since", "data_registo"],
    "customer_id": ["id", "cust_id", "client_id", "customerid", "customer_number", "account_id"],
}
ALIAS_LOOKUP = {a: canon for canon, alist in ALIASES.items() for a in alist + [canon]}
CANONICAL_ORDER = ["customer_id", "first_name", "last_name", "full_name", "email", "phone", "company",
                   "address", "city", "state", "postal_code", "country", "date_of_birth", "signup_date"]
DATE_COLUMNS = {"date_of_birth", "signup_date"}

COUNTRIES = {
    "PT": ["portugal", "pt", "prt", "portuguese republic"],
    "US": ["us", "usa", "u.s.", "u.s.a.", "united states", "united states of america", "america", "eua"],
    "GB": ["uk", "u.k.", "gb", "gbr", "united kingdom", "great britain", "england", "scotland", "wales",
           "reino unido"],
    "ES": ["es", "esp", "spain", "espana", "españa", "espanha"],
    "FR": ["fr", "fra", "france", "franca", "frança"],
    "DE": ["de", "deu", "germany", "deutschland", "alemanha"],
    "IT": ["it", "ita", "italy", "italia", "itália"],
    "BR": ["br", "bra", "brazil", "brasil"],
    "IE": ["ie", "irl", "ireland", "irlanda"],
    "NL": ["nl", "nld", "netherlands", "holland", "the netherlands", "holanda", "países baixos"],
    "BE": ["be", "bel", "belgium", "belgica", "bélgica"],
    "CH": ["ch", "che", "switzerland", "suica", "suíça"],
    "CA": ["ca", "can", "canada", "canadá"],
    "AO": ["ao", "ago", "angola"],
    "MZ": ["mz", "moz", "mozambique", "mocambique", "moçambique"],
    "CV": ["cv", "cpv", "cape verde", "cabo verde"],
}
COUNTRY_LOOKUP = {v: code for code, names in COUNTRIES.items() for v in names}
DIALING_CODES = {"PT": "351", "US": "1", "GB": "44", "ES": "34", "FR": "33", "DE": "49", "IT": "39",
                 "BR": "55", "IE": "353", "NL": "31", "BE": "32", "CH": "41", "CA": "1", "AO": "244",
                 "MZ": "258", "CV": "238"}

EMAIL_RE = re.compile(r"^[a-z0-9._%+'-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$")
EMAIL_DOMAIN_TYPOS = {
    "gmial.com": "gmail.com", "gmai.com": "gmail.com", "gmail.co": "gmail.com", "gamil.com": "gmail.com",
    "gmail.con": "gmail.com", "gnail.com": "gmail.com", "hotmial.com": "hotmail.com",
    "hotmail.con": "hotmail.com", "hotmai.com": "hotmail.com", "yahoo.con": "yahoo.com",
    "yaho.com": "yahoo.com", "outlok.com": "outlook.com", "outlook.con": "outlook.com",
}
NAME_PARTICLES = {"da", "de", "do", "das", "dos", "e", "van", "von", "der", "den", "la", "le", "di", "du", "del"}


def slugify(header):
    s = header.strip().lower().replace("\ufeff", "")
    s = re.sub(r"[^\w]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")


def read_csv(path):
    raw = Path(path).read_bytes()
    for enc in ENCODINGS:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    # The header line rarely contains stray delimiters, unlike csv.Sniffer's data sample.
    header_line = text.lstrip().split("\n", 1)[0]
    delimiter = max(",;\t|", key=header_line.count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    return rows, enc, delimiter


def map_headers(headers, overrides):
    mapped, used = [], set()
    for h in headers:
        slug = slugify(h)
        canon = overrides.get(h.strip()) or overrides.get(slug) or ALIAS_LOOKUP.get(slug, slug) or "column"
        name, n = canon, 2
        while name in used:  # keep duplicates distinct
            name = f"{canon}_{n}"
            n += 1
        used.add(name)
        mapped.append(name)
    return mapped


def clean_whitespace(v):
    v = v.replace("\u00a0", " ").replace("\r", " ").replace("\n", " ")
    v = re.sub(r"\s+", " ", v).strip().strip('"').strip("'").strip()
    return "" if v.lower() in NULL_TOKENS else v


def fix_name(v):
    if not v:
        return v
    if not (v.isupper() or v.islower()):
        return v  # respect deliberate mixed case like "McDonald" or "DeVries"

    def cap(word, first):
        if not first and word in NAME_PARTICLES:
            return word
        parts = re.split(r"([-'’])", word)
        out = "".join(p.capitalize() if i % 2 == 0 else p for i, p in enumerate(parts))
        if re.match(r"^mc[a-z]", word):
            out = "Mc" + out[2:].capitalize()
        return out

    words = v.lower().split(" ")
    return " ".join(cap(w, i == 0) for i, w in enumerate(words))


def fix_email(v):
    if not v:
        return v, None
    e = v.lower().replace(" ", "").replace(",", ".").rstrip(".")
    e = re.sub(r"^mailto:", "", e)
    e = re.sub(r"\.\.+", ".", e)
    if "@" in e:
        local, _, domain = e.rpartition("@")
        domain = EMAIL_DOMAIN_TYPOS.get(domain, domain)
        e = f"{local}@{domain}"
    return e, (None if EMAIL_RE.match(e) else "invalid email")


def fix_phone(v, default_cc):
    if not v:
        return v, None
    v = re.split(r"(?i)\s*(?:ext\.?|x|#)\s*\d+$", v)[0]
    has_plus = v.strip().startswith("+") or v.strip().startswith("00")
    digits = re.sub(r"\D", "", v)
    if v.strip().startswith("00"):
        digits = digits[2:]
    if len(digits) < 7 or len(digits) > 15:
        return v, "invalid phone length"
    if has_plus:
        return "+" + digits, None
    if default_cc:
        if digits.startswith(default_cc) and len(digits) >= len(default_cc) + 8:
            return "+" + digits, None  # country code typed without "+"
        return "+" + default_cc + re.sub(r"^0", "", digits), None  # drop national trunk prefix
    return digits, None


def date_parts(v):
    m = re.match(r"^(\d{1,4})[./\-\s](\d{1,2})[./\-\s](\d{2,4})(?:[ T].*)?$", v)
    return tuple(int(x) for x in m.groups()) if m else None


def infer_date_order(values):
    votes = Counter()
    for v in values:
        p = date_parts(v)
        if not p or p[0] > 31:
            continue
        if p[0] > 12:
            votes["dmy"] += 1
        elif p[1] > 12:
            votes["mdy"] += 1
    if votes["dmy"] and votes["mdy"]:
        return None, "conflicting"
    if votes:
        return votes.most_common(1)[0][0], "inferred"
    return None, "ambiguous"


def fix_date(v, order):
    if not v:
        return v, None
    p = date_parts(v)
    try:
        if p:
            a, b, c = p
            if a > 31 or order == "ymd":
                y, m, d = a, b, c
            elif order == "mdy":
                m, d, y = a, b, c
            else:
                d, m, y = a, b, c
            if y < 100:
                y += 2000 if y <= date.today().year % 100 else 1900
            return date(y, m, d).isoformat(), None
        for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%B %d, %Y", "%b %d, %Y", "%Y%m%d"):
            try:
                return datetime.strptime(v.replace(",", ", ").replace("  ", " "), fmt).date().isoformat(), None
            except ValueError:
                continue
    except ValueError:
        pass
    return v, "unparseable date"


def fix_country(v):
    if not v:
        return v, None
    code = COUNTRY_LOOKUP.get(v.lower().strip("."))
    return (code, None) if code else (v, "unknown country")


def fix_postal(v):
    return re.sub(r"\s*-\s*", "-", v.upper()) if v else v


def split_full_name(row):
    """Reorder "Smith, John" to "John Smith"; fill empty first/last columns when they exist."""
    full = row.get("full_name", "")
    changed = False
    if full.count(",") == 1:
        last, _, first = full.partition(",")
        full = row["full_name"] = f"{first.strip()} {last.strip()}"
        changed = True
    if full and "first_name" in row and "last_name" in row and not (row["first_name"] or row["last_name"]):
        row["first_name"], _, row["last_name"] = full.partition(" ")
        changed = True
    return changed


def dedupe(rows, keys):
    """Merge rows sharing any non-empty key value; first row wins, blanks filled from later rows."""
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen = {}
    for i, row in enumerate(rows):
        exact = ("__row__", tuple(sorted(row.items())))
        for k in [exact] + [(key, row.get(key, "").lower()) for key in keys if row.get(key)]:
            if k in seen:
                parent[find(i)] = find(seen[k])
            else:
                seen[k] = i
    groups = defaultdict(list)
    for i in range(len(rows)):
        groups[find(i)].append(i)
    merged, merges = [], []
    for root in sorted(groups):
        idxs = groups[root]
        base = dict(rows[idxs[0]])
        for j in idxs[1:]:
            for col, val in rows[j].items():
                if val and not base.get(col):
                    base[col] = val
        merged.append(base)
        if len(idxs) > 1:
            merges.append([rows[i]["__source_row__"] for i in idxs])
    return merged, merges


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--out-dir", default=".tmp")
    ap.add_argument("--dry-run", action="store_true", help="print the report only; write nothing")
    ap.add_argument("--date-order", choices=["auto", "dmy", "mdy", "ymd"], default="auto")
    ap.add_argument("--default-country-code", default="", help="dialing code for phones without one, e.g. 351")
    ap.add_argument("--dedupe-keys", default="email,phone")
    ap.add_argument("--no-dedupe", action="store_true")
    ap.add_argument("--map", action="append", default=[], help='header override, e.g. "Cust Mail=email"')
    args = ap.parse_args()

    rows, encoding, delimiter = read_csv(args.input)
    if not rows:
        sys.exit("ERROR: input file is empty")
    overrides = {}
    for m in args.map:
        src, _, dst = m.partition("=")
        overrides[src.strip()] = overrides[slugify(src)] = dst.strip()
    original_headers = rows[0]
    headers = map_headers(original_headers, overrides)
    stats = Counter()
    issues = []

    records = []
    for n, raw in enumerate(rows[1:], start=2):
        if len(raw) != len(headers):
            stats["rows_with_wrong_field_count"] += 1
            issues.append({"source_row": n, "column": "*", "value": delimiter.join(raw),
                           "problem": f"expected {len(headers)} fields, got {len(raw)}"})
            raw = (raw + [""] * len(headers))[:len(headers)]
        rec = {}
        for h, v in zip(headers, raw):
            cleaned = clean_whitespace(v)
            if cleaned != v:
                stats["values_trimmed_or_nulled"] += 1
            rec[h] = cleaned
        if not any(rec.values()):
            stats["empty_rows_dropped"] += 1
            continue
        rec["__source_row__"] = n
        records.append(rec)

    date_orders = {}
    for col in [h for h in headers if h in DATE_COLUMNS or "date" in h]:
        if args.date_order != "auto":
            date_orders[col] = (args.date_order, "forced")
        else:
            order, how = infer_date_order(r[col] for r in records)
            date_orders[col] = (order or "dmy", how if order else f"{how} - defaulted to dmy, confirm with user")

    def note(rec, col, before, after, problem, stat):
        if problem:
            issues.append({"source_row": rec["__source_row__"], "column": col, "value": before, "problem": problem})
            stats[f"invalid_{col}"] += 1
        elif after != before:
            stats[stat] += 1

    for rec in records:
        if split_full_name(rec):
            stats["full_names_split"] += 1
        for col in list(rec):
            v = rec[col]
            base = re.sub(r"_\d+$", "", col)
            if base in ("first_name", "last_name", "full_name", "city"):
                rec[col] = fix_name(v)
                note(rec, col, v, rec[col], None, "names_recased")
            elif base == "email":
                rec[col], prob = fix_email(v)
                note(rec, col, v, rec[col], prob, "emails_fixed")
            elif base == "phone":
                country = fix_country(rec.get("country", ""))[0]
                rec[col], prob = fix_phone(v, DIALING_CODES.get(country, args.default_country_code))
                note(rec, col, v, rec[col], prob, "phones_normalized")
            elif col in date_orders:
                rec[col], prob = fix_date(v, date_orders[col][0])
                note(rec, col, v, rec[col], prob, "dates_normalized")
            elif base == "country":
                rec[col], prob = fix_country(v)
                note(rec, col, v, rec[col], prob, "countries_normalized")
            elif base == "postal_code":
                rec[col] = fix_postal(v)
                note(rec, col, v, rec[col], None, "postal_codes_normalized")

    merges = []
    if not args.no_dedupe:
        keys = [k.strip() for k in args.dedupe_keys.split(",") if k.strip() in headers]
        before = len(records)
        records, merges = dedupe(records, keys)
        stats["duplicates_merged"] = before - len(records)

    ordered = [c for c in CANONICAL_ORDER if c in headers] + [c for c in headers if c not in CANONICAL_ORDER]
    stem = Path(args.input).stem
    out = Path(args.out_dir)
    report = {
        "input": str(args.input),
        "encoding": encoding,
        "delimiter": delimiter,
        "rows_in": len(rows) - 1,
        "rows_out": len(records),
        "header_mapping": dict(zip(original_headers, headers)),
        "unmapped_columns": [h for h in headers if h not in CANONICAL_ORDER],
        "date_orders": {c: {"order": o, "how": h} for c, (o, h) in date_orders.items()},
        "changes": dict(sorted(stats.items())),
        "issue_count": len(issues),
        "issues_sample": issues[:15],
        "duplicate_groups_sample": merges[:10],
    }
    if not args.dry_run:
        (out / "csv").mkdir(parents=True, exist_ok=True)
        (out / "json").mkdir(parents=True, exist_ok=True)
        clean_path = out / "csv" / f"{stem}_clean.csv"
        issues_path = out / "csv" / f"{stem}_issues.csv"
        report_path = out / "json" / f"{stem}_report.json"
        with open(clean_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=ordered, extrasaction="ignore")
            w.writeheader()
            w.writerows(records)
        with open(issues_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["source_row", "column", "value", "problem"])
            w.writeheader()
            w.writerows(issues)
        report["outputs"] = {"clean": str(clean_path), "issues": str(issues_path), "report": str(report_path)}
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
