"""Copy every row from the local docker Postgres into the Neon database the app
is now configured for (settings.database_url). Faithful column-for-column copy;
TRUNCATEs each Neon table first and resets integer sequences. Read-only on local."""
import asyncio, json, re
import asyncpg
from app.config import settings

LOCAL = "postgresql://app:app_password@localhost:5433/app_db"
NEON = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
NEON_ARGS = settings.db_connect_args  # ssl etc.

# parents first (no FK enforced, but keep it sane); int-PK tables need seq reset
ORDER = ["users", "user_01", "journey", "children", "insights", "purchases",
         "onboarding_visit", "email"]
INT_PK = {"users", "onboarding_visit", "email"}

async def cols(conn, table):
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name=$1 ORDER BY ordinal_position", table)
    return [r["column_name"] for r in rows]

async def main():
    src = await asyncpg.connect(LOCAL)
    dst = await asyncpg.connect(NEON, **NEON_ARGS)
    for c in (src, dst):
        await c.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads,
                               schema="pg_catalog")
    try:
        # truncate Neon in reverse order
        for t in reversed(ORDER):
            await dst.execute(f'TRUNCATE TABLE "{t}" RESTART IDENTITY CASCADE')
        for t in ORDER:
            colnames = await cols(src, t)
            collist = ", ".join(f'"{c}"' for c in colnames)
            rows = await src.fetch(f'SELECT {collist} FROM "{t}"')
            if rows:
                ph = ", ".join(f"${i+1}" for i in range(len(colnames)))
                await dst.executemany(
                    f'INSERT INTO "{t}" ({collist}) VALUES ({ph})',
                    [tuple(r[c] for c in colnames) for r in rows])
            n = await dst.fetchval(f'SELECT count(*) FROM "{t}"')
            print(f"  {t:18} local={len(rows):5}  neon={n:5}  {'OK' if n==len(rows) else 'MISMATCH'}")
        for t in INT_PK:
            await dst.execute(
                f"SELECT setval(pg_get_serial_sequence('{t}','id'), "
                f"COALESCE((SELECT MAX(id) FROM \"{t}\"),0)+1, false)")
        print("  sequences reset.")
    finally:
        await src.close(); await dst.close()

asyncio.run(main())
