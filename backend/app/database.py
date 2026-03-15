from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables():
    """Create all tables on startup. Use Alembic for production migrations."""
    async with engine.begin() as conn:
        # pgvector extension must exist before any vector columns are created
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        from app import models  # noqa: F401 — registers all ORM models
        await conn.run_sync(Base.metadata.create_all)

        # document_chunks uses a native pgvector column (vector(384)).
        # Managed with raw SQL so pgvector operators (<=> cosine distance) work correctly.
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                business_id UUID NOT NULL,
                content     TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                embedding   vector(384),
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_chunks_business_id
            ON document_chunks (business_id)
        """))
        # IVFFlat index — guard creation with a DO block to avoid duplicate errors
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE tablename = 'document_chunks'
                    AND indexname   = 'idx_chunks_embedding'
                ) THEN
                    CREATE INDEX idx_chunks_embedding
                    ON document_chunks USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 50);
                END IF;
            END$$;
        """))
