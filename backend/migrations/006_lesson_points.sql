-- Dàn ý giảng của từng bài: các ý chính rút từ nguồn tri thức (bỏ giới thiệu chương, hộp mục tiêu, hoạt động, bài tập).
-- LUSIA giảng theo dàn ý thay vì từng đoạn SGK thô; giáo viên xem / sửa trên trang kiểm duyệt.
CREATE TABLE lesson_points (
  lesson_id uuid NOT NULL REFERENCES lessons ON DELETE CASCADE,
  position  smallint NOT NULL CHECK (position >= 0),     -- 0 = mở bài (tình huống mở đầu của sách), 1.. = ý chính
  title     text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
  content   text NOT NULL CHECK (length(content) BETWEEN 1 AND 3000),  -- kiến thức nêu thẳng + ví dụ trong sách
  question  text CHECK (length(question) BETWEEN 1 AND 500),          -- câu hỏi kiểm tra (ưu tiên bài luyện tập của sách)
  answer    text CHECK (length(answer) BETWEEN 1 AND 500),
  chunk_ids bigint[] NOT NULL DEFAULT '{}',               -- đoạn SGK nguồn (chữ, hình) để trích dẫn trang
  PRIMARY KEY (lesson_id, position),
  CHECK ((question IS NULL) = (answer IS NULL)),
  CHECK (position > 0 OR question IS NULL)                -- mở bài không có câu hỏi kiểm tra
);
