CREATE TABLE courses (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL
);
CREATE TABLE modules (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id),
    name TEXT NOT NULL COLLATE NOCASE,
    created_at TEXT NOT NULL,
    UNIQUE (course_id, name)
);
CREATE TABLE topics (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id),
    name TEXT NOT NULL COLLATE NOCASE,
    created_at TEXT NOT NULL,
    UNIQUE (course_id, name)
);
CREATE TABLE module_topics (
    module_id INTEGER NOT NULL REFERENCES modules(id),
    topic_id INTEGER NOT NULL REFERENCES topics(id),
    PRIMARY KEY (module_id, topic_id)
);
CREATE TABLE gemini_usage (
    day TEXT PRIMARY KEY,
    requests INTEGER NOT NULL DEFAULT 0,
    exhausted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE traces (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    label TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT
);
CREATE TABLE trace_steps (
    id INTEGER PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES traces(id),
    seq INTEGER NOT NULL,
    step_type TEXT NOT NULL,
    component TEXT,
    input_json TEXT,
    output_json TEXT,
    model TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    duration_ms INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE threads (
    id TEXT PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    title TEXT,
    last_agent TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
