"""
All pgvector operations — storing and searching document chunks.
Uses raw SQL via SQLAlchemy text() so pgvector operators work correctly
with asyncpg without needing the pgvector-python package.
"""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.embeddings import vec_to_pg


async def store_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    business_id: uuid.UUID,
    chunks: list[str],
    embeddings: list[list[float]],
) -> int:
    """Insert all chunks for a document. Returns number of chunks stored."""
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        await db.execute(
            text("""
                INSERT INTO document_chunks
                    (document_id, business_id, content, chunk_index, embedding)
                VALUES
                    (:doc_id, :biz_id, :content, :idx, :emb::vector)
            """),
            {
                "doc_id":  str(document_id),
                "biz_id":  str(business_id),
                "content": chunk,
                "idx":     i,
                "emb":     vec_to_pg(embedding),
            },
        )
    await db.commit()
    return len(chunks)


async def search_chunks(
    db: AsyncSession,
    business_id: uuid.UUID,
    query_embedding: list[float],
    limit: int = 5,
    min_similarity: float = 0.25,
) -> list[dict]:
    """
    Find the most relevant chunks for this business using cosine similarity.
    Returns list of {content, similarity, document_id} dicts.
    Only returns chunks with similarity >= min_similarity.
    """
    result = await db.execute(
        text("""
            SELECT
                dc.content,
                dc.document_id,
                1 - (dc.embedding <=> :q::vector) AS similarity,
                d.original_name
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.business_id = :biz_id
              AND d.status = 'ready'
            ORDER BY dc.embedding <=> :q::vector
            LIMIT :lim
        """),
        {
            "q":      vec_to_pg(query_embedding),
            "biz_id": str(business_id),
            "lim":    limit,
        },
    )
    rows = result.fetchall()
    return [
        {
            "content":     row.content,
            "document_id": str(row.document_id),
            "filename":    row.original_name,
            "similarity":  round(float(row.similarity), 3),
        }
        for row in rows
        if float(row.similarity) >= min_similarity
    ]


async def delete_chunks_for_document(
    db: AsyncSession,
    document_id: uuid.UUID,
) -> None:
    """Remove all chunks belonging to a document (called on document delete)."""
    await db.execute(
        text("DELETE FROM document_chunks WHERE document_id = :doc_id"),
        {"doc_id": str(document_id)},
    )
    await db.commit()
