-- Documents, conversations and ingest jobs (SDD 4.3). Tables for genres, structure,
-- relations and reviews come in later migrations, with the features that use them.
-- Deviations from SDD 4.3: indexed_versions replaces document_versions.collection, since
-- one version is indexed once per retrieval configuration; conversations.pinned,
-- turns.missing, citations.section/page and the job's upload_path/version_id/error_code
-- serve the web UI and job recovery.

CREATE TABLE tenants (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);

CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  genre_id TEXT NOT NULL DEFAULT 'unknown',
  current_version_id TEXT REFERENCES document_versions(id),
  title TEXT,
  doc_number TEXT,
  validity_status TEXT NOT NULL DEFAULT 'unknown',  -- in_force | partly_expired | expired | unknown
  status TEXT NOT NULL DEFAULT 'ready',             -- ready | deleting
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL);
CREATE INDEX documents_tenant ON documents(tenant_id, status);

CREATE TABLE document_versions (
  id TEXT PRIMARY KEY,                              -- first 32 hex digits of the file's SHA-256
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'ready',
  file_name TEXT NOT NULL,
  file_ext TEXT NOT NULL,
  file_size INTEGER NOT NULL,
  stored_path TEXT NOT NULL,
  pages INTEGER,
  ingested_at TEXT NOT NULL,
  UNIQUE (document_id, seq));

CREATE TABLE indexed_versions (
  version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  collection TEXT NOT NULL,
  n_chunks INTEGER NOT NULL,
  indexed_at TEXT NOT NULL,
  PRIMARY KEY (version_id, collection));

CREATE TABLE conversations (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  title TEXT,
  pinned INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL);

CREATE TABLE turns (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  question TEXT NOT NULL,
  answer TEXT,
  status TEXT NOT NULL,                             -- processing | answered | partial | not_found | failed
  missing TEXT,
  warnings TEXT NOT NULL DEFAULT '[]',              -- JSON [{sentence_index, reason}]
  config TEXT NOT NULL,                             -- JSON: the settings that produced the answer (NFR-12)
  latency_ms INTEGER,
  created_at TEXT NOT NULL);

CREATE TABLE turn_scope (
  turn_id TEXT NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  PRIMARY KEY (turn_id, document_id));

CREATE TABLE citations (
  turn_id TEXT NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
  label TEXT NOT NULL,
  chunk_id TEXT NOT NULL,                           -- logical key into Qdrant
  document_id TEXT NOT NULL,                        -- copied, so BR10 deletes by SQL alone
  version_id TEXT NOT NULL,
  section TEXT NOT NULL,
  page INTEGER,
  sentence_index INTEGER,
  verdict TEXT NOT NULL,                            -- supported | unsupported | unchecked
  PRIMARY KEY (turn_id, label));
CREATE INDEX citations_document ON citations(document_id);

CREATE TABLE ingest_jobs (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  file_name TEXT NOT NULL,
  status TEXT NOT NULL,                             -- queued | running | done | duplicate | failed
  stage TEXT,
  progress REAL,
  error_code TEXT,
  error TEXT,
  upload_path TEXT,                                 -- the uploaded file until it is ingested
  document_id TEXT,                                 -- set up front for a new version
  version_id TEXT,
  created_at TEXT NOT NULL,
  finished_at TEXT);
