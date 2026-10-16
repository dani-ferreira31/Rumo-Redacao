"""Enfileira um job manualmente.

Uso: python -m scripts.enqueue system.ping '{"msg": "oi"}'
"""

import argparse
import asyncio
import json

from app.core.db import SessionLocal, engine
from app.jobs.queue import enqueue


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue")
    parser.add_argument("payload", nargs="?", default="{}")
    args = parser.parse_args()
    async with SessionLocal() as session:
        job = await enqueue(session, args.queue, json.loads(args.payload))
        await session.commit()
        print(f"job {job.id} enfileirado em {args.queue}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
