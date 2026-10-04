-- Tiến độ & lỗi khi nạp tài liệu (document-ingestion)
ALTER TABLE documents
  ADD COLUMN page_count      smallint CHECK (page_count >= 1),
  ADD COLUMN processed_pages smallint NOT NULL DEFAULT 0 CHECK (processed_pages >= 0),
  ADD COLUMN skipped_figures smallint NOT NULL DEFAULT 0 CHECK (skipped_figures >= 0),  -- hình mô tả thất bại
  ADD COLUMN error           text,                                                       -- "<bước>: <lỗi>"
  ADD COLUMN updated_at      timestamptz NOT NULL DEFAULT now(),
  -- failed ⇔ có lỗi: không có "failed mà không rõ lý do" hay "ready mà còn lỗi"
  ADD CONSTRAINT documents_error_iff_failed CHECK ((status = 'failed') = (error IS NOT NULL));
