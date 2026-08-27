"""Full data migration: Xano -> local Postgres. THE cutover dry-run tool.

Extract  — read every table via the Metadata API `/content` endpoint (read-only).
Transform— convert Xano's wire types to the local column types: epoch-ms ints to
           timestamptz, "Y-m-d" strings to date, dicts to jsonb, uuid strings to
           uuid; nulls and empty-strings preserved per Appendix A.
Load     — TRUNCATE the target tables and insert, preserving primary keys, in one
           transaction; integer sequences are reset afterwards. No FK constraints
           exist locally, so load order is free and Xano orphans do not block.

    python3 scripts/migrate_from_xano.py            # fresh extract from live Xano (read-only)
    python3 scripts/migrate_from_xano.py --from-backup backups/<stamp>
    python3 scripts/migrate_from_xano.py --dry-run  # extract+transform+count, no writes

Passwords are copied verbatim. They are peppered and the port cannot verify them
(settled 2026-08-27); this preserves the data for a later lazy-migration login path.
"""
import argparse, asyncio, json, sys, uuid as uuidlib
from datetime import datetime, timezone, date
from pathlib import Path
import urllib.request, urllib.parse, urllib.error
import asyncpg

META = "https://xnrw-fohw-scw8.a2.xano.io/api:meta"
PAT_FILE = Path.home() / ".config/xano/pat"
DB = "postgresql://app:app_password@localhost:5433/app_db"

# Xano table name -> (id, local table). Order is load order (parents first, though
# no FK is enforced). session is Xano auth-token state; it has no local table.
TABLES = [
    ("user", 1, "users"),
    ("User_01", 6, "user_01"),
    ("Journey", 8, "journey"),
    ("children", 7, "children"),
    ("Insights", 9, "insights"),
    ("Purchases", 10, "purchases"),
    ("onboarding_visit", 13, "onboarding_visit"),
    ("Email", 12, "email"),
]
INT_PK = {"users", "onboarding_visit", "email"}

# ---- transforms -------------------------------------------------------------
def dt_ms(v):
    if v is None or v == "":
        return None
    return datetime.fromtimestamp(int(v) / 1000, tz=timezone.utc)

def as_date(v):
    if v is None or v == "":
        return None
    if isinstance(v, str):
        return date.fromisoformat(v[:10])
    return datetime.fromtimestamp(int(v) / 1000, tz=timezone.utc).date()

def as_uuid(v):
    if not v:
        return None
    try:
        return uuidlib.UUID(str(v))
    except ValueError:
        return None

def s(v):  # keep string as-is, incl "" (never coerce "" to null)
    return v

# per target-table: list of (target_col, source_key, transform)
COLS = {
    "users": [("id","id",int),("created_at","created_at",dt_ms),("name","name",s),
        ("email","email",s),("password","password",s),("account_id","account_id",int),
        ("role","role",s),("password_reset","password_reset",lambda v:v),("otp","otp",s),
        ("otp_expiry","otp_expiry",dt_ms),("relationship_focus","relationship_focus",s)],
    "user_01": [("id","id",as_uuid),("created_at","created_at",dt_ms),("name","name",s),
        ("memberstack_id","memberstack_id",s),("email","email",s),("password","password",s),
        ("date_of_birth","date_of_birth",as_date),("time_of_birth","time_of_birth",dt_ms),
        ("lat","lat",float),("lon","lon",float),("pronoun","pronoun",s)],
    "journey": [("id","id",as_uuid),("created_at","created_at",dt_ms),("title","title",s),
        ("desc","desc",s),("number","number",lambda v:None if v is None else int(v)),("image","image",s)],
    "children": [("id","id",as_uuid),("created_at","created_at",dt_ms),("user_01_id","user_01_id",as_uuid),
        ("user_id","user_id",lambda v:None if v is None else int(v)),("name","name",s),
        ("date_of_birth","date_of_birth",as_date),("time_of_birth","time_of_birth",dt_ms),
        ("lat","lat",lambda v:None if v is None else float(v)),("lon","lon",lambda v:None if v is None else float(v)),
        ("pronoun","pronoun",s),("default_child","default_child",bool),("relationship_focus","relationship_focus",s)],
    "insights": [("id","id",as_uuid),("created_at","created_at",dt_ms),("real_user_id","real_user_id",lambda v:None if v is None else int(v)),
        ("child_id","child_id",as_uuid),("journey_id","journey_id",as_uuid),("status","status",s),
        ("deep_text","deep_text",s),("summary_text","summary_text",s),("teaser_text","teaser_text",s),
        ("request_id","request_id",as_uuid),("last_error","last_error",s),("insights_api_payload","insights_api_payload",lambda v:v)],
    "purchases": [("id","id",as_uuid),("created_at","created_at",dt_ms),("user_id","user_id",lambda v:None if v is None else int(v)),
        ("child_id","child_id",as_uuid),("journey_id","journey_id",as_uuid),("purchase_source","purchase_source",s),
        ("purchase_reference","purchase_reference",s),("email","email",s)],
    "onboarding_visit": [("id","id",int),("created_at","created_at",dt_ms),("session_id","session_id",s),
        ("flow","flow",s),("step","step",s),("step_index","step_index",int)],
    "email": [("id","id",int),("created_at","created_at",dt_ms),("email","email",s),("subject","subject",s),
        ("html_content","html_content",s),("timestamp","timestamp",dt_ms),("delivered","delivered",bool)],
}

# ---- extract ----------------------------------------------------------------
def fetch_live(table_id, tok):
    rows, page = [], 1
    while True:
        q = urllib.parse.urlencode({"per_page": 100, "page": page})
        req = urllib.request.Request(f"{META}/workspace/1/table/{table_id}/content?{q}",
                                     headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        items = data.get("items", data if isinstance(data, list) else [])
        rows += items
        if len(items) < 100:
            break
        page += 1
    return rows

def fetch_backup(xano_name, backup_dir):
    # backup filenames use the Xano table name with its own casing
    fmap = {"user":"user","User_01":"User_01","Journey":"Journey","children":"children",
            "Insights":"Insights","Purchases":"Purchases","onboarding_visit":"onboarding_visit","Email":"Email"}
    f = Path(backup_dir) / f"{fmap[xano_name]}.json"
    d = json.load(open(f))
    return d.get("items", d) if isinstance(d, dict) else d

# ---- run --------------------------------------------------------------------
async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-backup")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tok = PAT_FILE.read_text().strip() if not args.from_backup else None
    extracted = {}
    for xname, tid, local in TABLES:
        raw = fetch_backup(xname, args.from_backup) if args.from_backup else fetch_live(tid, tok)
        rows = []
        for src in raw:
            rows.append(tuple(fn(src.get(sk)) for (_c, sk, fn) in COLS[local]))
        extracted[local] = rows
        print(f"  extract {xname:18} -> {local:18} {len(rows):5} rows")

    if args.dry_run:
        print("\n[dry-run] no writes."); return

    conn = await asyncpg.connect(DB)
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    try:
        async with conn.transaction():
            for _x, _t, local in reversed(TABLES):
                await conn.execute(f'TRUNCATE TABLE "{local}" RESTART IDENTITY CASCADE')
            for _x, _t, local in TABLES:
                cols = COLS[local]
                collist = ", ".join(f'"{c}"' for c, _sk, _fn in cols)
                ph = ", ".join(f"${i+1}" for i in range(len(cols)))
                await conn.executemany(
                    f'INSERT INTO "{local}" ({collist}) VALUES ({ph})', extracted[local])
                print(f"  load    {local:18} {len(extracted[local]):5} rows")
            # reset integer-id sequences
            for local in INT_PK:
                await conn.execute(
                    f"SELECT setval(pg_get_serial_sequence('{local}','id'), "
                    f"COALESCE((SELECT MAX(id) FROM \"{local}\"),0)+1, false)")
        print("\n  committed.")
    finally:
        await conn.close()

    # verify
    conn = await asyncpg.connect(DB)
    print("\n  VERIFY (loaded vs extracted):")
    ok = True
    for _x, _t, local in TABLES:
        n = await conn.fetchval(f'SELECT count(*) FROM "{local}"')
        match = "OK " if n == len(extracted[local]) else "MISMATCH"
        if n != len(extracted[local]): ok = False
        print(f"    {local:18} db={n:5}  src={len(extracted[local]):5}  {match}")
    await conn.close()
    print("\n  ALL COUNTS MATCH" if ok else "\n  COUNT MISMATCH — investigate")

asyncio.run(main())
