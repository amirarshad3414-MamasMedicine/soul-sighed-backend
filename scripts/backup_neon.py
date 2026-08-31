"""Dump every Neon table to JSON before a destructive reload.

    python3 scripts/backup_neon.py            # writes backups/neon-<stamp>/<table>.json

Values are JSON-safe: timestamps become ISO-8601 strings, uuids become strings.
Restore is manual (the dump preserves everything the migration would wipe).
"""
import asyncio, json, sys
from datetime import datetime, timezone, date
from pathlib import Path
import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings

TABLES = ["users", "user_01", "journey", "children", "insights", "purchases",
          "onboarding_visit", "email"]


def jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if v is None or isinstance(v, (str, int, float, bool, dict, list)):
        return v
    return str(v)  # uuid and anything else


async def main():
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    ssl = "require" if "neon.tech" in dsn else None
    out = Path(__file__).resolve().parents[1] / "backups" / (
        "neon-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    out.mkdir(parents=True)

    conn = await asyncpg.connect(dsn, ssl=ssl)
    try:
        for t in TABLES:
            rows = await conn.fetch(f'SELECT * FROM "{t}" ORDER BY created_at NULLS LAST')
            data = [{k: jsonable(v) for k, v in r.items()} for r in rows]
            (out / f"{t}.json").write_text(json.dumps(data, ensure_ascii=False))
            print(f"  backup {t:18} {len(data):5} rows")
    finally:
        await conn.close()
    print(f"\n  written to {out}")

asyncio.run(main())
