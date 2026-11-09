CREATE UNIQUE INDEX IF NOT EXISTS idx_trace_steps_trace_seq ON trace_steps(trace_id, seq);
