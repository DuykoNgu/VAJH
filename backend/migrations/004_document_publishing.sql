-- Chuẩn bị tri thức tách khỏi học: tài liệu là BẢN NHÁP cho tới khi giáo viên kiểm duyệt và xuất bản
ALTER TABLE documents
  ADD COLUMN published_at timestamptz,
  ADD COLUMN published_by uuid REFERENCES teachers ON DELETE SET NULL,
  -- chỉ tài liệu đã xử lý xong mới được xuất bản
  ADD CONSTRAINT documents_published_only_ready CHECK (published_at IS NULL OR status = 'ready');

-- Dữ liệu cũ: tài liệu đã sẵn sàng trước khi có kiểm duyệt coi như đã xuất bản (không làm mất bài đang học)
UPDATE documents SET published_at = now() WHERE status = 'ready';
