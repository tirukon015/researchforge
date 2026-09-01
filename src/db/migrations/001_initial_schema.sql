-- ============================================================
-- ResearchForge, Migration 001: Initial schema
-- ============================================================
-- Milestone 2: Database Foundation
--
-- ⚠️  TARGET: the ResearchForge Supabase project ONLY.
--     Before running this, confirm the SUPABASE_URL host matches
--     the ResearchForge project. NEVER run against RPOMS.
--
-- SAFETY: this migration is ADDITIVE ONLY.
--   It contains no DROP, no TRUNCATE, no DELETE, and no destructive
--   ALTER. Every statement uses IF NOT EXISTS, so re-running it is
--   safe and produces no error.
--
-- HOW TO RUN:
--   Supabase Dashboard -> SQL Editor -> New query
--   -> paste this whole file -> Run
-- ============================================================


-- ------------------------------------------------------------
-- 1. Enable the pgvector extension
-- ------------------------------------------------------------
-- This teaches Postgres a new column type, `vector`, plus the
-- distance operators used for similarity search. Without it,
-- `vector(1024)` below is an unknown type and the migration fails.
CREATE EXTENSION IF NOT EXISTS vector;


-- ------------------------------------------------------------
-- 2. papers: one row per uploaded research paper
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS papers (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Owner of the paper. NULL until authentication ships (feature E5).
    -- Kept now so multi-user support is an UPDATE, not a schema rewrite.
    user_id          uuid,

    -- Bibliographic metadata (extracted during ingestion in Milestone 3)
    title            text NOT NULL,
    authors          text[],
    year             integer,

    -- The stored file
    filename         text NOT NULL,
    storage_path     text,
    file_size_bytes  bigint,
    page_count       integer,

    -- Ingestion lifecycle. The CHECK constraint means an invalid status
    -- is rejected by the database itself, not just by application code.
    status           text NOT NULL DEFAULT 'processing'
                     CHECK (status IN ('processing', 'ready', 'failed')),
    error_message    text,

    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  papers IS 'One row per uploaded research paper.';
COMMENT ON COLUMN papers.status IS
    'processing = ingesting; ready = searchable; failed = see error_message';


-- ------------------------------------------------------------
-- 3. chunks: the searchable pieces of each paper, with vectors
-- ------------------------------------------------------------
-- A paper is split into overlapping chunks. Each chunk is embedded
-- into a 1024-number vector. Similarity search runs over this table.
CREATE TABLE IF NOT EXISTS chunks (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ON DELETE CASCADE: deleting a paper automatically deletes its
    -- chunks. Without this, orphaned vectors would linger forever and
    -- pollute every future search result.
    paper_id              uuid NOT NULL
                          REFERENCES papers(id) ON DELETE CASCADE,

    chunk_index           integer NOT NULL,
    content               text    NOT NULL,

    -- page_number is what makes academic citations possible. Without it
    -- the assistant can quote a paper but cannot say WHERE it came from,
    -- which makes the output unusable for a literature review.
    page_number           integer,
    section_title         text,
    token_count           integer,

    -- ⚠️ 1024 is PERMANENT for this column.
    -- It matches jina-embeddings-v3 (default size) and sits well under
    -- pgvector's 2000-dimension limit for HNSW / IVFFlat indexes.
    -- Changing it requires re-embedding every paper (see PROJECT_PLAN §F).
    embedding             vector(1024),

    -- Provenance: records WHICH model produced this vector. This is what
    -- makes a future provider migration safe, you can tell at a glance
    -- which rows still need re-embedding, instead of silently mixing
    -- vectors from two different models (which returns garbage results).
    embedding_model       text    NOT NULL,
    embedding_dimensions  integer NOT NULL,

    created_at            timestamptz NOT NULL DEFAULT now(),

    -- A paper cannot have two chunks at the same position.
    -- Makes re-ingestion idempotent instead of duplicating rows.
    CONSTRAINT chunks_paper_chunk_unique UNIQUE (paper_id, chunk_index)
);

COMMENT ON TABLE  chunks IS 'Searchable text chunks with their embedding vectors.';
COMMENT ON COLUMN chunks.page_number IS
    'Source page. Required for citations. Do not drop.';
COMMENT ON COLUMN chunks.embedding IS
    'vector(1024) from jina-embeddings-v3. Dimension is permanent.';
COMMENT ON COLUMN chunks.embedding_model IS
    'Model that produced this vector. Enables safe provider migration.';


-- ------------------------------------------------------------
-- 4. Indexes
-- ------------------------------------------------------------
-- Without a vector index, every search scans EVERY row. Fine for 50
-- chunks, unusable at 20,000. HNSW is chosen over IVFFlat because it
-- gives better recall and needs no training data to be present first.
--
-- vector_cosine_ops = compare by cosine similarity, which is the correct
-- measure for text embeddings (it compares direction, not magnitude).
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

-- Speeds up "give me all chunks for this paper" and the cascade delete.
CREATE INDEX IF NOT EXISTS chunks_paper_id_idx ON chunks (paper_id);

-- Speeds up the library listing (newest first) and status polling.
CREATE INDEX IF NOT EXISTS papers_created_at_idx ON papers (created_at DESC);
CREATE INDEX IF NOT EXISTS papers_status_idx     ON papers (status);


-- ------------------------------------------------------------
-- 5. Keep updated_at accurate automatically
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'papers_set_updated_at'
    ) THEN
        CREATE TRIGGER papers_set_updated_at
            BEFORE UPDATE ON papers
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
END $$;


-- ------------------------------------------------------------
-- 6. Row Level Security
-- ------------------------------------------------------------
-- RLS is enabled now so the tables are locked down by default.
--
-- With RLS enabled and NO permissive policy, the public `anon` key can
-- read nothing. The backend uses the service-role key, which bypasses
-- RLS, so the API keeps working while the database stays closed to the
-- browser. Per-user policies are added with authentication (feature E5).
ALTER TABLE papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;


-- ------------------------------------------------------------
-- 7. Verification
-- ------------------------------------------------------------
-- After running, this should return: papers, chunks
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('papers', 'chunks')
ORDER BY table_name;
