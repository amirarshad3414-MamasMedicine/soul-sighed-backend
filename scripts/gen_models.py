#!/usr/bin/env python3
"""Generate SQLModel table models from the dumped Xano table schemas.

One module per domain under app/models/. Output is committed and then
hand-edited; re-run only when a Xano schema changes, and diff the result.

Rules, each derived from the dump or from live rows rather than assumed:

  * `nullable` describes the column, `required` describes the *input*. Treating
    "not required" as nullable lets NULLs into columns Xano forbids —
    children.name is required=False, nullable=False, and every live row holds "".
  * Xano writes "" in `default` to mean "this type's zero value". Which zero
    depends on the type. NOT NULL columns get it as a Postgres server default so
    inserts that omit the column behave as they do in Xano.
  * enum columns become plain `str`: 384/505 children.relationship_focus and
    1/332 Insights.status are empty strings a strict Enum would reject.
  * Only `access=internal` is suppressed on the wire; `access=private`
    (created_at) is returned. Confirmed against 505 children / 332 Insights.
  * Timestamps are stored tz-aware; the epoch-millisecond serialisation Xano
    uses on the wire belongs in the response schema, not the column.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")

# xano table -> (module, class, postgres table name)
# `user` is renamed because it is reserved in Postgres; the rest keep their Xano
# names so the deferred data migration stays a straight copy.
LAYOUT = {
    "user":             ("user",      "User",            "users"),
    "User_01":          ("user",      "LegacyUser",      "user_01"),
    "children":         ("child",     "Child",           "children"),
    "Insights":         ("insight",   "Insight",         "insights"),
    "Journey":          ("insight",   "Journey",         "journey"),
    "Purchases":        ("purchase",  "Purchase",        "purchases"),
    "Email":            ("email",     "EmailMessage",    "email"),
    "onboarding_visit": ("analytics", "OnboardingVisit", "onboarding_visit"),
}

TYPE_MAP = {
    "int": "int", "text": "str", "email": "str", "password": "str",
    "timestamp": "datetime", "date": "date", "decimal": "float", "bool": "bool",
    "uuid": "UUID", "enum": "str", "object": "dict", "json": "dict",
    "tableref": "int", "tablerefuuid": "UUID",
}
JSON_TYPES = {"object", "json"}
# The SQL text of each type's zero value. These are SQL fragments, so a string
# zero must carry its own quotes: text("''") is an empty string, text('') is an
# empty fragment and silently produces no default at all.
ZERO_SQL = {"str": '"\'\'"', "int": '"0"', "float": '"0"',
            "bool": '"false"', "dict": '"\'{}\'"'}
QUOTED_TYPES = {"str", "dict"}

INDEX_NOTES = {
    ("children", ("user_01_id", "name", "date_of_birth")):
        "user_01_id is NULL in every row and Postgres treats NULLs as distinct,"
        " so this never fires. add_children checks user_id instead. 52 duplicate"
        " rows exist today. Reproduced for parity — see triage.",
}


def server_default_for(field: dict, py: str, nullable: bool) -> str | None:
    """Postgres server default matching Xano's column default, or None."""
    raw = field.get("default")
    if raw == "now" and py == "datetime":
        return "func.now()"
    if nullable:
        return None
    if raw not in (None, ""):
        # An explicit literal: 'child' on children.relationship_focus, '0' on
        # children.user_id. String types need SQL quotes of their own — without
        # them Postgres reads DEFAULT child as a column reference.
        literal = f"'{raw}'" if py in QUOTED_TYPES else str(raw)
        return f'text("{literal}")'
    if py == "datetime":
        return "text(\"'epoch'\")"   # see xano-export/parity-questions.md
    zero = ZERO_SQL.get(py)
    return f"text({zero})" if zero else None


def column_assignment(name: str, py: str, xano_type: str, nullable: bool,
                      default: str | None) -> str:
    """The right-hand side of a model field declaration."""
    if name == "id":
        return (" = Field(default=None, primary_key=True)" if py == "int"
                else " = Field(default_factory=uuid4, primary_key=True)")

    if xano_type in JSON_TYPES:
        parts = ["JSONB"]
        if default:
            parts.append(f"server_default={default}")
        if not nullable:
            parts.append("nullable=False")
        return f" = Field(default=None, sa_column=Column({', '.join(parts)}))"

    if py == "datetime":
        parts = ["DateTime(timezone=True)"]
        if default:
            parts.append(f"server_default={default}")
        if not nullable:
            parts.append("nullable=False")
        return f" = Field(default=None, sa_column=Column({', '.join(parts)}))"

    # Everything else: let SQLModel infer the SQL type, and spell out only the
    # column keywords. Using sa_column here would defeat that inference.
    if not nullable or default:
        parts = ["default=None"]
        if not nullable:
            parts.append("nullable=False")
        if default:
            parts.append(f'sa_column_kwargs={{"server_default": {default}}}')
        return f" = Field({', '.join(parts)})"
    return " = None"


def render(schema: dict, class_name: str, table_name: str) -> tuple[str, set[str]]:
    needs: set[str] = set()
    hidden: list[str] = []
    columns: list[str] = []

    for field in schema.get("_schema") or []:
        name, xano_type = field["name"], field.get("type")
        py = TYPE_MAP.get(xano_type, "str")
        nullable = bool(field.get("nullable"))
        default = server_default_for(field, py, nullable)

        if py == "date":
            needs.add("date")
        if py == "datetime":
            needs.update({"datetime", "sa_datetime"})
        if py == "UUID":
            needs.add("uuid")
        if xano_type in JSON_TYPES:
            needs.add("json")
        if default == "func.now()":
            needs.add("func")
        elif default:
            needs.add("text")
        if field.get("access") == "internal":
            hidden.append(name)

        annotation = py if (name == "id" or not nullable) else f"{py} | None"
        assign = column_assignment(name, py, xano_type, nullable, default)

        comment = []
        if field.get("values"):
            comment.append(f"xano enum {field['values']}; str because '' occurs")
        if field.get("access"):
            comment.append(f"access={field['access']}")
        columns.append(f"    {name}: {annotation}{assign}"
                       + (f"  # {'; '.join(comment)}" if comment else ""))

    constraints: list[str] = []
    for index in schema.get("_index") or []:
        cols = tuple(f.get("name") if isinstance(f, dict) else f
                     for f in (index.get("fields") or []))
        if not cols or index.get("type") == "primary":
            continue
        note = INDEX_NOTES.get((table_name, cols))
        if note:
            constraints.append(f"        # NOTE: {note}")
        args = ", ".join(repr(c) for c in cols)
        suffix = "_".join(cols)
        if index.get("type") == "unique":
            needs.add("constraint")
            constraints.append(
                f'        UniqueConstraint({args}, name="uq_{table_name}_{suffix}"),')
        else:
            needs.add("index")
            constraints.append(f'        Index("ix_{table_name}_{suffix}", {args}),')

    table_args = ""
    if constraints:
        table_args = "\n    __table_args__ = (\n" + "\n".join(constraints) + "\n    )\n"

    body = (
        f'class {class_name}(SQLModel, table=True):\n'
        f'    """Xano table `{schema["name"]}` (id {schema["id"]}).\n\n'
        f'    `created_at` is a real timestamp column. Xano serialises it as epoch\n'
        f'    milliseconds on the wire — that conversion lives in the response\n'
        f'    schema. See xano-export/formats.md.\n'
        f'    """\n\n'
        f'    __tablename__ = "{table_name}"\n'
        f'{table_args}\n'
        + "\n".join(columns) + "\n"
    )
    if hidden:
        needs.add("classvar")
        body += f"\n    HIDDEN_FIELDS: ClassVar[list[str]] = {hidden!r}\n"
    return body, needs


def header(needs: set[str]) -> str:
    stdlib: list[str] = []
    if "classvar" in needs:
        stdlib.append("from typing import ClassVar")
    dt = sorted(n for n in needs if n in ("date", "datetime"))
    if dt:
        stdlib.append(f"from datetime import {', '.join(dt)}")
    if "uuid" in needs:
        stdlib.append("from uuid import UUID, uuid4")

    sa_names = set()
    if "json" in needs or "sa_datetime" in needs:
        sa_names.add("Column")
    if "sa_datetime" in needs:
        sa_names.add("DateTime")
    if "index" in needs:
        sa_names.add("Index")
    if "constraint" in needs:
        sa_names.add("UniqueConstraint")
    if "func" in needs:
        sa_names.add("func")
    if "text" in needs:
        sa_names.add("text")

    third: list[str] = []
    if sa_names:
        third.append(f"from sqlalchemy import {', '.join(sorted(sa_names))}")
    if "json" in needs:
        third.append("from sqlalchemy.dialects.postgresql import JSONB")
    third.append("from sqlmodel import Field, SQLModel")

    return "\n".join(stdlib + [""] + third) + "\n\n\n"


def main() -> None:
    schemas = {}
    for path in (ROOT / "xano-export/table").glob("*.json"):
        data = json.load(open(path))
        schemas[data["name"]] = data

    modules: dict[str, list[tuple[str, set[str]]]] = {}
    for xano_name, (module, class_name, table) in LAYOUT.items():
        if xano_name not in schemas:
            print(f"  !! no dumped schema for {xano_name}", file=sys.stderr)
            continue
        modules.setdefault(module, []).append(
            render(schemas[xano_name], class_name, table))

    dest = ROOT / "app/models"
    dest.mkdir(parents=True, exist_ok=True)
    for module, parts in modules.items():
        needs: set[str] = set().union(*(n for _, n in parts))
        (dest / f"{module}.py").write_text(
            header(needs) + "\n\n".join(body for body, _ in parts))
        print(f"  app/models/{module}.py  ({len(parts)} model{'s' if len(parts) > 1 else ''})")

    by_module: dict[str, list[str]] = {}
    for module, class_name, _ in LAYOUT.values():
        by_module.setdefault(module, []).append(class_name)

    init = ['"""Every model must be imported here — Alembic discovers tables through',
            'SQLModel.metadata, and a model that is never imported is never created."""',
            ""]
    for module in sorted(by_module):
        init.append(f"from app.models.{module} import {', '.join(sorted(by_module[module]))}")
    all_classes = sorted(c for cs in by_module.values() for c in cs)
    init += ["", "__all__ = ["] + [f'    "{c}",' for c in all_classes] + ["]", ""]
    (dest / "__init__.py").write_text("\n".join(init))
    print(f"  app/models/__init__.py  ({len(all_classes)} exports)")


if __name__ == "__main__":
    main()
