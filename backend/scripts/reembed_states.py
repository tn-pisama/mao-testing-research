#!/usr/bin/env python
"""Re-embed all states with the new E5-large model.

Run after migration 002_upgrade_embeddings_1024.
Usage: python scripts/reembed_states.py [--batch-size=100] [--dry-run]
"""
import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.core.embeddings import get_embedder
from app.storage.models import State


async def reembed_states(batch_size: int = 100, dry_run: bool = False):
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    embedder = get_embedder()
    embedder.warmup()
    
    total_processed = 0
    total_updated = 0
    
    async with async_session() as session:
        result = await session.execute(select(State.id, State.response_redacted))
        states = result.fetchall()
        
        print(f"Found {len(states)} states to process")
        
        for i in range(0, len(states), batch_size):
            batch = states[i:i + batch_size]
            
            texts = []
            state_ids = []
            for state_id, response in batch:
                if response and len(response.strip()) > 0:
                    texts.append(response)
                    state_ids.append(state_id)
            
            if not texts:
                continue
            
            embeddings = embedder.encode(texts, batch_size=batch_size)
            
            if not dry_run:
                for state_id, embedding in zip(state_ids, embeddings):
                    await session.execute(
                        update(State)
                        .where(State.id == state_id)
                        .values(embedding=embedding.tolist())
                    )
                await session.commit()
            
            total_processed += len(batch)
            total_updated += len(texts)
            
            print(f"Processed {total_processed}/{len(states)} states, updated {total_updated} embeddings")
    
    await engine.dispose()
    
    action = "Would update" if dry_run else "Updated"
    print(f"\n{action} {total_updated} embeddings out of {total_processed} states")


def main():
    parser = argparse.ArgumentParser(description="Re-embed states with E5-large model")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()
    
    asyncio.run(reembed_states(batch_size=args.batch_size, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
