-- Runs once, on first initialisation of the postgres data volume.
-- The application also creates these at startup (init_db), so this file is a
-- convenience for tools that connect before the API has ever booted.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
