-- Trace agent + LLM để debug và đánh giá (xem /monitor). Mỗi lượt học / vào bài / nghe thử / nạp sách = 1 trace.
CREATE TABLE traces (
  id          uuid PRIMARY KEY,
  kind        text NOT NULL CHECK (kind IN ('lesson_start', 'turn', 'preview', 'ingest')),
  session_id  uuid REFERENCES learning_sessions ON DELETE SET NULL,  -- đặt lại dữ liệu demo vẫn giữ lịch sử giám sát
  document_id uuid REFERENCES documents ON DELETE SET NULL,
  started_at  timestamptz NOT NULL,
  duration_ms integer NOT NULL CHECK (duration_ms >= 0),
  status      text NOT NULL CHECK (status IN ('ok', 'error')),
  error       text,
  input       text,
  output      text,
  rating      smallint CHECK (rating IN (-1, 1)),
  note        text,
  rated_by    uuid REFERENCES teachers ON DELETE SET NULL,
  CHECK ((status = 'error') = (error IS NOT NULL))
);
CREATE INDEX ON traces (started_at DESC);
CREATE INDEX ON traces (session_id);
CREATE INDEX ON traces (document_id);
CREATE INDEX ON traces (rated_by);

CREATE TABLE trace_spans (
  trace_id      uuid NOT NULL REFERENCES traces ON DELETE CASCADE,
  seq           smallint NOT NULL,           -- thứ tự bắt đầu trong trace
  parent_seq    smallint,                    -- span cha (LLM nằm trong agent)
  kind          text NOT NULL CHECK (kind IN ('agent', 'llm')),
  name          text NOT NULL,               -- tên agent hoặc route LLM
  offset_ms     integer NOT NULL CHECK (offset_ms >= 0),  -- bắt đầu sau đầu trace bao lâu
  duration_ms   integer NOT NULL CHECK (duration_ms >= 0),
  status        text NOT NULL CHECK (status IN ('ok', 'refusal', 'error')),
  model         text,
  effort        text,
  input_tokens  integer,
  output_tokens integer,
  detail        jsonb NOT NULL DEFAULT '{}',  -- agent: mode, handoff, citations; llm: system, messages, response, error
  PRIMARY KEY (trace_id, seq),
  FOREIGN KEY (trace_id, parent_seq) REFERENCES trace_spans (trace_id, seq)
);
CREATE INDEX ON trace_spans (trace_id, parent_seq);
