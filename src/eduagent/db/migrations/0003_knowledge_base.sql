ALTER TABLE courses ADD COLUMN week1_monday TEXT;

CREATE TABLE files (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id),
    module_id INTEGER REFERENCES modules(id),
    origin TEXT NOT NULL CHECK (origin IN ('module', 'reference')),
    kind TEXT NOT NULL CHECK (kind IN ('pdf', 'pptx', 'docx', 'txt', 'md', 'paste', 'web')),
    title TEXT NOT NULL,
    source_name TEXT NOT NULL,
    stored_path TEXT,
    content_hash TEXT,
    layout TEXT CHECK (layout IS NULL OR layout IN ('slides', 'document', 'docx', 'text', 'markdown', 'web')),
    status TEXT NOT NULL CHECK (status IN
        ('queued', 'reading', 'chunking', 'embedding', 'tagging', 'done', 'failed', 'skipped')),
    error TEXT,
    queue_pos INTEGER NOT NULL UNIQUE,
    pages_total INTEGER,
    pieces_total INTEGER,
    pieces_done INTEGER NOT NULL DEFAULT 0,
    uploaded_at TEXT NOT NULL,
    uploaded_week INTEGER NOT NULL,
    topics_state TEXT NOT NULL DEFAULT 'none' CHECK (topics_state IN ('none', 'pending', 'reviewed', 'failed')),
    replaces_file_id INTEGER,
    trace_id TEXT,
    UNIQUE (course_id, content_hash)
);

CREATE TABLE file_pieces (
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    piece INTEGER NOT NULL,
    first_page INTEGER,
    last_page INTEGER,
    done INTEGER NOT NULL DEFAULT 0,
    carry_json TEXT,
    PRIMARY KEY (file_id, piece)
);

CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id),
    course_id INTEGER NOT NULL,
    module_id INTEGER,
    origin TEXT NOT NULL,
    kind TEXT NOT NULL,
    seq INTEGER NOT NULL,
    text TEXT NOT NULL,
    heading_path TEXT,
    loc_kind TEXT,
    loc_start INTEGER,
    loc_end INTEGER,
    word_count INTEGER NOT NULL
);
CREATE INDEX idx_chunks_file_seq ON chunks(file_id, seq);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    chunk_id UNINDEXED, heading, text,
    tokenize = "porter unicode61 tokenchars '_'"
);

CREATE TABLE topic_suggestions (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    chunk_seqs_json TEXT NOT NULL,
    match TEXT NOT NULL CHECK (match IN ('existing', 'similar', 'new')),
    match_topic_id INTEGER REFERENCES topics(id)
);

CREATE TABLE chunk_topics (
    chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (chunk_id, topic_id)
);

CREATE TABLE removed_chunks (
    chunk_id TEXT PRIMARY KEY,
    file_id INTEGER NOT NULL,
    file_title TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ('deleted', 'replaced')),
    removed_at TEXT NOT NULL
);
