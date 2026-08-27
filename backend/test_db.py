import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test():
    e = create_async_engine(
        "postgresql+asyncpg://daarag:daarag@localhost:5432/rag_research_paper",
        echo=True,
    )
    try:
        async with e.connect() as c:
            r = await c.execute(text("SELECT 1"))
            print("SUCCESS:", r.scalar())
    except Exception as ex:
        print(f"FAILED: {type(ex).__name__}: {ex}")
    finally:
        await e.dispose()

asyncio.run(test())
