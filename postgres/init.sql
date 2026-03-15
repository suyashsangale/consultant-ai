-- This runs once when the Postgres container is first created.
-- Enables the pgvector extension so vector columns work.
CREATE EXTENSION IF NOT EXISTS vector;
