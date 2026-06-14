import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import AsyncSessionLocal
from app.models import KnowledgeItem
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(KnowledgeItem))
        items = res.scalars().all()
        for i in items:
            print(f"Title: {i.title}")
            print(f"  Chunk Count: {i.chunk_count}")
            print(f"  Qdrant Point Count: {len(i.qdrant_point_ids)}")
            print(f"  Active: {i.is_active}")
            print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())
