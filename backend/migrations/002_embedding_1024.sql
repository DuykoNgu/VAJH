-- Embedding chính: AITeamVN/Vietnamese_Embedding_v2 (1024 chiều, thay text-embedding-3-small 1536 chiều).
-- Vector cũ không dùng lại được: có dòng chunks thì migration lỗi → xóa chunks rồi embed lại tài liệu.
ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(1024);
