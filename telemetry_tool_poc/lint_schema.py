"""SQL lint for the Supabase schema migration.

The migration must be idempotent, so it uses `create table if not exists` for
new tables and `alter table ... add column if not exists` for columns that may
already exist. That means a foreign key can be added *before* the column it
references exists, which only fails at runtime on an existing database where
`create table if not exists` was a no-op.

This script checks, for every foreign key, that the local column, the
referenced table, and the referenced column are all defined *earlier in the
file* than the constraint itself.
"""

import re
import sys

CREATE_TABLE_RE = re.compile(
    r"create table\s+if not exists\s+public\.(\w+)\s*\(", re.IGNORECASE
)
ADD_COLUMN_RE = re.compile(
    r"alter table\s+public\.(\w+)\s+add column if not exists\s+(\w+)",
    re.IGNORECASE,
)
FK_RE = re.compile(
    r"alter table\s+public\.(\w+)\s+add constraint\s+(\w+)\s+"
    r"foreign key\s*\(\s*(\w+)\s*\)\s*references\s+public\.(\w+)\s*\(\s*(\w+)\s*\)",
    re.IGNORECASE,
)
COLUMN_LINE_RE = re.compile(
    r"^\s*(\w+)\s+(?!key\b|unique\b|primary\b|references\b|check\b|constraint\b|generated\b)",
    re.IGNORECASE,
)


def extract_block(text, open_index):
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return text[open_index + 1:index]
    return ""


def collect_definitions(text):
    """Map (table, column) -> file offset where it first becomes available."""
    defined = {}

    for match in CREATE_TABLE_RE.finditer(text):
        table = match.group(1).lower()
        body = extract_block(text, match.end() - 1)
        depth = 0
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("--"):
                continue
            depth += raw_line.count("(") - raw_line.count(")")
            if depth > 0:
                continue
            column_match = COLUMN_LINE_RE.match(raw_line)
            if column_match:
                defined.setdefault((table, column_match.group(1).lower()), match.start())

    for match in ADD_COLUMN_RE.finditer(text):
        key = (match.group(1).lower(), match.group(2).lower())
        if key not in defined:
            defined[key] = match.start()

    tables = {}
    for match in CREATE_TABLE_RE.finditer(text):
        tables.setdefault(match.group(1).lower(), match.start())

    return defined, tables


def main(path):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()

    defined, tables = collect_definitions(text)

    errors = []
    checked = 0
    for match in FK_RE.finditer(text):
        table, constraint, column, ref_table, ref_column = [part.lower() for part in match.groups()]
        checked += 1
        position = match.start()

        local = defined.get((table, column))
        if local is None:
            errors.append(f"FK {constraint}: column {table}.{column} is never created or added.")
        elif local > position:
            errors.append(
                f"FK {constraint}: column {table}.{column} is added after the constraint."
            )

        table_position = tables.get(ref_table)
        if table_position is None:
            errors.append(f"FK {constraint}: referenced table public.{ref_table} is never created.")
        elif table_position > position:
            errors.append(
                f"FK {constraint}: referenced table public.{ref_table} is created after the constraint."
            )

        referenced = defined.get((ref_table, ref_column))
        if referenced is None:
            errors.append(f"FK {constraint}: referenced column public.{ref_table}.{ref_column} is never created.")
        elif referenced > position:
            errors.append(
                f"FK {constraint}: referenced column public.{ref_table}.{ref_column} is added after the constraint."
            )

    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    print(f"OK: {checked} foreign keys reference columns and tables defined earlier in the migration.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "telemetry_tool_poc/supabase_setup.sql"))