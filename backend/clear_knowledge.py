import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import AsyncSessionLocal
from app.models import KnowledgeItem
from sqlalchemy import delete

async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(KnowledgeItem))
        await db.commit()
        print("Cleared all knowledge items from database.")

if __name__ == "__main__":
    asyncio.run(main())
