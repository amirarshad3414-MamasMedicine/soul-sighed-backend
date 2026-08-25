"""Shared plumbing for the Phase 8 parity scripts.

A *pair* is one captured request plus the live-Xano response to it, stored as
JSON under xano-export/responses/pairs/. `capture_responses.py` writes pairs
(live traffic — gated on approval); `diff_responses.py` replays each pair's
request against the local FastAPI port and compares **shape, not values**
(migration plan 8.2): Xano holds real data and FastAPI holds seed data, so
identical values are impossible by construction.

Shape means: status code, JSON-ness, key sets (order-independent), JSON type
per key, and the null-vs-empty convention per key. On top of that,
`contract_check` enforces the per-key formats of Appendix A
(xano-export/formats.md) on each side independently.

Everything under xano-export/responses/ is gitignored — captured bodies carry
real user data (emails, children's names and birth dates).
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESPONSES_DIR = ROOT / "xano-export" / "responses"
PAIRS_DIR = RESPONSES_DIR / "pairs"
RUNS_DIR = RESPONSES_DIR / "runs"
INVENTORY = ROOT / "xano-export" / "inventory.csv"

# The live app API group (`scripters`, canonical uUEiFEze) and the Metadata API.
XANO_APP_BASE = "https://xnrw-fohw-scw8.a2.xano.io/api:uUEiFEze"
META_BASE = "https://xnrw-fohw-scw8.a2.xano.io/api:meta"
WORKSPACE = 1

# From xano-export/table/*.json (filename prefix = table id).
TABLE_IDS = {
    "user": 1,
    "account": 2,
    "event_log": 3,
    "User_01": 6,
    "children": 7,
    "Journey": 8,
    "Insights": 9,
    "Purchases": 10,
    "session": 11,
    "Email": 12,
    "onboarding_visit": 13,
}


def slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")


def live_endpoints(path: Path = INVENTORY) -> list[str]:
    """Endpoint names the coverage gate runs over: group 4, triage PORT."""
    with open(path, newline="") as f:
        return sorted(
            row["endpoint"]
            for row in csv.DictReader(f)
            if row["group"].startswith("4_") and row["triage"].strip().upper() == "PORT"
        )


# --- pair storage ------------------------------------------------------------

def pair_filename(pair: dict) -> str:
    return f"{pair['order']:03d}_{slug(pair['endpoint'])}__{slug(pair['case'])}.json"


def save_pair(pair: dict) -> Path:
    PAIRS_DIR.mkdir(parents=True, exist_ok=True)
    out = PAIRS_DIR / pair_filename(pair)
    out.write_text(json.dumps(pair, indent=2, default=str))
    return out


def load_pairs(only: str | None = None) -> list[dict]:
    pairs = []
    if PAIRS_DIR.is_dir():
        for f in PAIRS_DIR.glob("*.json"):
            pair = json.loads(f.read_text())
            pair["_file"] = f.name
            if only is None or pair["endpoint"] == only:
                pairs.append(pair)
    return sorted(pairs, key=lambda p: p["order"])


def coverage(pairs: list[dict], endpoints: list[str]) -> tuple[list[str], list[str]]:
    """(covered, missing) endpoint names — the 8.3 gate fails on any missing."""
    have = {p["endpoint"] for p in pairs}
    return sorted(have & set(endpoints)), sorted(set(endpoints) - have)


# --- shape signatures --------------------------------------------------------

def kind_of(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):  # before int — bool is an int subclass
        return "bool"
    if isinstance(v, (int, float)):
        return "number"  # Appendix A: lat/lon arrive as int OR float; one class
    if isinstance(v, str):
        return "empty-string" if v == "" else "string"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "object"
    raise TypeError(f"not a JSON value: {type(v)}")


def shape_of(v) -> dict:
    """Recursive shape descriptor. List elements are merged into one element
    shape, so a list mixing null and string dobs reads as one nullable key."""
    k = kind_of(v)
    s: dict = {"kinds": {k}}
    if k == "object":
        s["keys"] = {key: shape_of(val) for key, val in v.items()}
        s["optional"] = set()
    elif k == "list":
        element = None
        for e in v:
            element = merge_shapes(element, shape_of(e))
        s["element"] = element  # None for an empty list
    return s


def merge_shapes(a: dict | None, b: dict | None) -> dict | None:
    if a is None:
        return b
    if b is None:
        return a
    out: dict = {"kinds": a["kinds"] | b["kinds"]}
    if "keys" in a or "keys" in b:
        ka, kb = a.get("keys", {}), b.get("keys", {})
        optional = set(a.get("optional", ())) | set(b.get("optional", ()))
        keys = {}
        for key in set(ka) | set(kb):
            if key in ka and key in kb:
                keys[key] = merge_shapes(ka[key], kb[key])
            else:
                keys[key] = ka.get(key) or kb[key]
                optional.add(key)  # absent from some elements
        out["keys"], out["optional"] = keys, optional
    if "element" in a or "element" in b:
        out["element"] = merge_shapes(a.get("element"), b.get("element"))
    return out


def diff_shapes(x: dict, l: dict, path: str, problems: list, warnings: list) -> None:
    """x = shape of the Xano response, l = shape of the local one."""
    xs, ls = x["kinds"], l["kinds"]
    if xs != ls:
        nx, nl = xs - {"null"}, ls - {"null"}
        strings = {"string", "empty-string"}
        if nx and nl and not (nx & nl) and not ((nx | nl) <= strings):
            problems.append(
                f"{path}: JSON type differs — xano={sorted(xs)}, local={sorted(ls)}")
        elif (nx | nl) <= strings and nx and nl and ("null" not in xs | ls):
            pass  # empty vs non-empty string is data, not shape
        elif ("null" in xs) != ("null" in ls):
            # With different data on each side, a nullable column showing null
            # on only one side is expected — but null-vs-"" convention breaks
            # (formats.md: per column, not per project) also land here. Flag,
            # don't fail.
            warnings.append(
                f"{path}: null on one side only (xano={sorted(xs)}, "
                f"local={sorted(ls)}) — check the column's null-vs-empty "
                f"convention in formats.md")
        else:
            warnings.append(
                f"{path}: kinds differ — xano={sorted(xs)}, local={sorted(ls)}")
    if "keys" in x and "keys" in l:
        xk, lk = x["keys"], l["keys"]
        for key in sorted(set(xk) - set(lk)):
            problems.append(
                f"{path}.{key}: on the Xano response, missing locally "
                f"(keys are never dropped — formats.md)")
        for key in sorted(set(lk) - set(xk)):
            problems.append(f"{path}.{key}: on the local response only")
        xopt, lopt = x.get("optional", set()), l.get("optional", set())
        for key in sorted(set(xk) & set(lk)):
            if key in lopt and key not in xopt:
                problems.append(
                    f"{path}.{key}: missing from some local rows but on "
                    f"every Xano row")
            elif key in xopt and key not in lopt:
                warnings.append(f"{path}.{key}: missing from some Xano rows")
            diff_shapes(xk[key], lk[key], f"{path}.{key}", problems, warnings)
    if "element" in x or "element" in l:
        xe, le = x.get("element"), l.get("element")
        if xe is not None and le is not None:
            diff_shapes(xe, le, f"{path}[]", problems, warnings)
        elif (xe is None) != (le is None):
            side = "local" if le is None else "Xano"
            warnings.append(
                f"{path}[]: list empty on the {side} side — element shape "
                f"unverifiable")


# --- Appendix A as code ------------------------------------------------------

def _epoch_ms(v):
    if isinstance(v, int) and not isinstance(v, bool) and v >= 10**12:
        return None
    return "must be an integer in epoch milliseconds"


def _date_or_null(v):
    if v is None or (isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)):
        return None
    return 'must be null or a "YYYY-MM-DD" string'


def _uuid_str(v):
    if isinstance(v, str) and v:
        return None
    return "must be a non-empty (uuid) string"


def _int(v):
    if isinstance(v, int) and not isinstance(v, bool):
        return None
    return "must be an integer"


def _num_or_null(v):
    if v is None or (isinstance(v, (int, float)) and not isinstance(v, bool)):
        return None
    return "must be null or a JSON number"


def _bool(v):
    if isinstance(v, bool):
        return None
    return 'must be true/false (not 0/1, not "")'


# Key names are contract-bearing wherever they appear in a response body.
# `id` carries no rule: it is a uuid string in children/Insights/Journey but an
# integer in `user`, so the name alone does not determine the format.
CONTRACT = {
    "created_at": _epoch_ms,
    "date_of_birth": _date_or_null,
    "child_id": _uuid_str,
    "journey_id": _uuid_str,
    "request_id": _uuid_str,
    "user_id": _int,
    "real_user_id": _int,
    "lat": _num_or_null,
    "lon": _num_or_null,
    "default_child": _bool,
}


def _walk_contract(value, path: str, out: list[tuple[str, str]]) -> None:
    if isinstance(value, dict):
        for key, val in value.items():
            rule = CONTRACT.get(key)
            if rule is not None:
                err = rule(val)
                if err:
                    out.append((key, f"{path}.{key}: {err} (got {val!r})"))
            _walk_contract(val, f"{path}.{key}", out)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _walk_contract(item, f"{path}[{i}]", out)


def contract_check(value, path: str = "body") -> list[str]:
    """Appendix A violations in one JSON value, applied at any nesting depth."""
    out: list[tuple[str, str]] = []
    _walk_contract(value, path, out)
    return [msg for _, msg in out]


def contract_violations(value, path: str = "body") -> list[tuple[str, str]]:
    """Same, as (key, message) — the key lets a violation on the Xano side
    excuse the same violation locally."""
    out: list[tuple[str, str]] = []
    _walk_contract(value, path, out)
    return out


# --- pair comparison ---------------------------------------------------------

def compare_pair(pair: dict, local_status: int, local_is_json: bool,
                 local_body) -> tuple[list[str], list[str]]:
    """(problems, warnings) for one replayed pair. Problems fail the diff."""
    problems: list[str] = []
    warnings: list[str] = []
    want = pair["response"]
    if want["status"] != local_status:
        problems.append(f"status: xano={want['status']} local={local_status}")
    xano_is_json = "json" in want
    if xano_is_json != local_is_json:
        problems.append(
            f"content: {'Xano' if xano_is_json else 'local'} side is JSON, "
            f"the other is not")
    elif xano_is_json:
        diff_shapes(shape_of(want["json"]), shape_of(local_body),
                    "body", problems, warnings)
        # Appendix A is derived from live rows, so where the live response
        # disagrees with it, reality wins (plan, Phase 4) and the doc is what
        # changes. Matching Xano on such a key must not fail the port — so a
        # key Xano violates is excused locally and reported on both sides.
        xano_bad = contract_violations(want["json"])
        excused = {key for key, _ in xano_bad}
        for key, viol in contract_violations(local_body):
            if key in excused:
                warnings.append(f"contract (local, excused): {viol}")
            else:
                problems.append(f"contract (local): {viol}")
        for _, viol in xano_bad:
            warnings.append(
                f"contract (XANO side!): {viol} — reality wins; "
                f"update formats.md")
        if isinstance(want["json"], dict) and isinstance(local_body, dict):
            mx, ml = want["json"].get("message"), local_body.get("message")
            if isinstance(mx, str) and isinstance(ml, str) and mx != ml:
                warnings.append(f"message text: xano={mx!r} local={ml!r}")
    return problems, warnings
