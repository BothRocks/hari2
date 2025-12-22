#!/usr/bin/env python3
"""Import documents from legacy HARI database (3-table schema) to new schema."""
import asyncio
import json
from uuid import UUID

import asyncpg


async def import_documents():
    """Import documents from hari_import_temp to hari2."""

    # Connect to source (old schema)
    source = await asyncpg.connect("postgresql://localhost:5432/hari_import_temp")

    # Connect to target (new schema)
    target = await asyncpg.connect("postgresql://localhost:5432/hari2")

    print("Connected to databases")

    # Query to join old tables
    query = """
        SELECT
            d.id,
            d.source_identifier as url,
            d.source_type,
            d.content_hash,
            COALESCE(s.title, d.title) as title,
            s.summary_text as summary,
            s.quick_summary,
            s.keywords,
            s.industries,
            COALESCE(s.language, d.language) as language,
            e.embedding,
            d.created_at,
            d.updated_at
        FROM documents d
        LEFT JOIN summaries s ON s.document_id = d.id
        LEFT JOIN document_embeddings e ON e.document_id = d.id AND e.embedding_type = 'full_document'
        WHERE d.status = 'completed'
    """

    rows = await source.fetch(query)
    print(f"Found {len(rows)} completed documents to import")

    # Check existing documents in target
    existing = await target.fetch("SELECT content_hash FROM documents WHERE content_hash IS NOT NULL")
    existing_hashes = {r['content_hash'] for r in existing}
    print(f"Target has {len(existing_hashes)} existing documents")

    imported = 0
    skipped = 0

    for row in rows:
        # Skip if already exists (by content hash)
        if row['content_hash'] in existing_hashes:
            skipped += 1
            continue

        # Convert keywords/industries arrays to JSON
        keywords = list(row['keywords']) if row['keywords'] else None
        industries = list(row['industries']) if row['industries'] else None

        # Convert embedding to list if present
        embedding = None
        if row['embedding']:
            embedding = str(row['embedding'])

        # Map source_type
        source_type = row['source_type'].upper() if row['source_type'] else 'URL'

        try:
            await target.execute("""
                INSERT INTO documents (
                    id, url, source_type, content_hash, title, summary,
                    quick_summary, keywords, industries, language,
                    embedding, processing_status, created_at, updated_at
                ) VALUES (
                    $1, $2, $3::sourcetype, $4, $5, $6,
                    $7, $8::json, $9::json, $10,
                    $11::vector, 'COMPLETED'::processingstatus, $12, $13
                )
            """,
                row['id'],
                row['url'],
                source_type,
                row['content_hash'],
                row['title'],
                row['summary'],
                row['quick_summary'],
                json.dumps(keywords) if keywords else None,
                json.dumps(industries) if industries else None,
                row['language'],
                embedding,
                row['created_at'],
                row['updated_at'],
            )
            imported += 1
            if imported % 20 == 0:
                print(f"  Imported {imported} documents...")
        except Exception as e:
            print(f"Error importing {row['id']}: {e}")

    print(f"\nImport complete: {imported} imported, {skipped} skipped (already exist)")

    # Verify
    count = await target.fetchval("SELECT COUNT(*) FROM documents WHERE processing_status = 'COMPLETED'")
    print(f"Total completed documents in hari2: {count}")

    await source.close()
    await target.close()


if __name__ == "__main__":
    asyncio.run(import_documents())
