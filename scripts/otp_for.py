"""Print the current OTP stored on Neon for an email (headful reset testing)."""
import asyncio, sys
from sqlalchemy import text
from app.database import engine
async def main():
    async with engine.connect() as c:
        r = (await c.execute(text("SELECT otp, otp_expiry FROM users WHERE email=:e"),
                             {"e": sys.argv[1]})).first()
    print(r[0] if r else "")
asyncio.run(main())
