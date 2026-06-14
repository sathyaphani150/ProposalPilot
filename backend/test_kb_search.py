import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.knowledge_service import search_knowledge

async def main():
    query = "HIPAA patient doctor communication Next.js"
    print(f"Searching Knowledge Base for: '{query}'...")
    results = await search_knowledge(query)
    for r in results:
        print(f"Title: {r.get('title')}")
        print(f"  Score: {r['score']:.4f}")
        print(f"  Text: {r['text'][:150]}...")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
