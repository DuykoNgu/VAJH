-- LUSIA – PostgreSQL + pgvector schema (MVP)
-- File gốc (PDF, ảnh) ở MinIO/S3; mọi thứ còn lại, kể cả embedding cho RAG, ở Postgres.
-- ponytail: UUIDv4 (gen_random_uuid) vì Postgres 16 chưa có uuidv7(); đổi khi lên PG18

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE subject AS ENUM (
  'toan', 'ngu_van', 'tieng_viet', 'tieng_anh', 'khtn', 'vat_ly', 'hoa_hoc',
  'sinh_hoc', 'lich_su', 'dia_ly', 'lich_su_dia_ly', 'tin_hoc', 'khac'
);
CREATE TYPE document_kind AS ENUM ('textbook', 'upload');
CREATE TYPE document_status AS ENUM ('processing', 'ready', 'failed');
CREATE TYPE message_role AS ENUM ('student', 'assistant');
CREATE TYPE agent_name AS ENUM ('orchestrator', 'tutor', 'knowledge', 'vision', 'document', 'assessment');
CREATE TYPE chunk_kind AS ENUM ('text', 'figure');
CREATE TYPE review_status AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE question_focus AS ENUM ('concept', 'figure');

-- ============ Người dùng ============
-- Học sinh đọc tên đăng nhập + mật khẩu bằng giọng nói (STT) hoặc nhờ người khác gõ hộ
CREATE TABLE users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name     text NOT NULL,
  username      text NOT NULL UNIQUE CHECK (username ~ '^[a-z0-9_.]{3,32}$'),  -- chữ thường, dễ đọc thành tiếng
  password_hash text NOT NULL,           -- argon2 / bcrypt, không bao giờ lưu mật khẩu gốc
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Vai trò = có dòng trong students / teachers → FK tự đảm bảo đúng vai trò
CREATE TABLE students (
  user_id     uuid PRIMARY KEY REFERENCES users ON DELETE CASCADE,
  grade       smallint NOT NULL CHECK (grade BETWEEN 1 AND 12),
  speech_rate numeric(3,2) NOT NULL DEFAULT 1.00 CHECK (speech_rate BETWEEN 0.50 AND 2.00)  -- tốc độ TTS
);

CREATE TABLE teachers (
  user_id uuid PRIMARY KEY REFERENCES users ON DELETE CASCADE
);

CREATE TABLE classes (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id uuid NOT NULL REFERENCES teachers ON DELETE RESTRICT,
  name       text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON classes (teacher_id);

CREATE TABLE class_students (
  class_id   uuid NOT NULL REFERENCES classes ON DELETE CASCADE,
  student_id uuid NOT NULL REFERENCES students ON DELETE CASCADE,
  PRIMARY KEY (class_id, student_id)
);
CREATE INDEX ON class_students (student_id);

-- ============ Học liệu ============
CREATE TABLE documents (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind        document_kind NOT NULL,
  title       text NOT NULL,
  subject     subject NOT NULL,
  grade       smallint NOT NULL CHECK (grade BETWEEN 1 AND 12),
  storage_key text NOT NULL UNIQUE,                        -- key file gốc trong MinIO / S3
  uploaded_by uuid REFERENCES users ON DELETE RESTRICT,   -- NULL = SGK do hệ thống nạp
  status      document_status NOT NULL DEFAULT 'processing',  -- OCR → cắt chunk → embed vào bảng chunks
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK ((kind = 'textbook') = (uploaded_by IS NULL))
);
CREATE INDEX ON documents (uploaded_by);
CREATE INDEX ON documents (subject, grade);

CREATE TABLE lessons (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents ON DELETE CASCADE,
  position    smallint NOT NULL,
  title       text NOT NULL,
  page_start  smallint NOT NULL,
  page_end    smallint NOT NULL,
  UNIQUE (document_id, position),
  CHECK (page_start BETWEEN 1 AND page_end)
);

-- Kho tri thức cho RAG: đoạn văn SGK + mô tả hình do Vision Agent viết (giáo viên duyệt)
CREATE TABLE chunks (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  document_id uuid NOT NULL REFERENCES documents ON DELETE CASCADE,
  lesson_id   uuid REFERENCES lessons ON DELETE CASCADE,   -- NULL = ngoài các bài (mục lục, phụ lục)
  page        smallint NOT NULL CHECK (page >= 1),
  kind        chunk_kind NOT NULL,
  content     text NOT NULL,
  embedding   vector(1536) NOT NULL,    -- phải khớp số chiều của model embedding đang dùng
  image_key   text,                     -- ảnh cắt của hình (S3)          ┐ chỉ có
  review      review_status,            -- giáo viên duyệt mô tả hình     ┘ khi kind = 'figure'
  reviewed_by uuid REFERENCES teachers ON DELETE SET NULL,
  reviewed_at timestamptz,
  CHECK ((kind = 'figure') = (image_key IS NOT NULL)),
  CHECK ((kind = 'figure') = (review IS NOT NULL)),
  CHECK ((coalesce(review, 'pending') <> 'pending') = (reviewed_at IS NOT NULL))
);
CREATE INDEX ON chunks (document_id);
CREATE INDEX ON chunks (lesson_id);
CREATE INDEX ON chunks (reviewed_by);
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON chunks (document_id) WHERE review = 'pending';  -- hàng chờ duyệt của giáo viên

-- ============ Phiên học & hội thoại ============
CREATE TABLE learning_sessions (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id uuid NOT NULL REFERENCES students ON DELETE CASCADE,
  lesson_id  uuid REFERENCES lessons ON DELETE SET NULL,  -- NULL = hỏi tự do, không gắn bài
  started_at timestamptz NOT NULL DEFAULT now(),
  ended_at   timestamptz,                                -- NULL = đang diễn ra
  CHECK (ended_at >= started_at)
);
CREATE INDEX ON learning_sessions (student_id, started_at DESC);
CREATE INDEX ON learning_sessions (lesson_id);

CREATE TABLE messages (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  session_id uuid NOT NULL REFERENCES learning_sessions ON DELETE CASCADE,
  role       message_role NOT NULL,
  agent      agent_name,              -- agent trả lời; NULL với tin của học sinh
  content    text NOT NULL,           -- transcript STT hoặc câu trả lời (không lưu audio gốc)
  image_key  text,                    -- ảnh học sinh chụp gửi kèm (S3)
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((role = 'assistant') = (agent IS NOT NULL))
);
CREATE INDEX ON messages (session_id, id);

-- ============ Đánh giá ============
CREATE TABLE quizzes (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id uuid NOT NULL REFERENCES students ON DELETE CASCADE,
  lesson_id  uuid NOT NULL REFERENCES lessons ON DELETE RESTRICT,  -- không âm thầm xóa kết quả học
  session_id uuid REFERENCES learning_sessions ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON quizzes (student_id, lesson_id);
CREATE INDEX ON quizzes (lesson_id);
CREATE INDEX ON quizzes (session_id);

CREATE TABLE questions (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  quiz_id        uuid NOT NULL REFERENCES quizzes ON DELETE CASCADE,
  position       smallint NOT NULL,
  prompt         text NOT NULL,
  focus          question_focus NOT NULL DEFAULT 'concept',  -- hỏi về kiến thức hay về hình vẽ
  choices        text[],              -- NULL = câu tự luận ngắn
  correct_answer text NOT NULL,
  explanation    text NOT NULL,
  UNIQUE (quiz_id, position),
  CHECK (choices IS NULL OR (cardinality(choices) BETWEEN 2 AND 6 AND correct_answer = ANY (choices)))
);

CREATE TABLE answers (
  question_id uuid PRIMARY KEY REFERENCES questions ON DELETE CASCADE,  -- mỗi câu trả lời 1 lần
  answer_text text NOT NULL,          -- transcript câu trả lời bằng giọng nói
  score       numeric(3,2) NOT NULL CHECK (score BETWEEN 0 AND 1),  -- 1 = đúng; tự luận chấm từng phần
  feedback    text NOT NULL,
  answered_at timestamptz NOT NULL DEFAULT now()
);

-- Điểm mạnh / yếu theo bài → Student Model + Teacher Dashboard
-- concept_mastery vs figure_mastery: hổng vì không hiểu bài hay vì không hình dung được hình
-- ponytail: view tính trực tiếp; đổi sang materialized view khi dashboard chậm
CREATE VIEW lesson_mastery AS
SELECT qz.student_id,
       qz.lesson_id,
       count(*)                                                    AS answered,
       round(avg(a.score), 2)                                      AS mastery,
       round(avg(a.score) FILTER (WHERE q.focus = 'concept'), 2)   AS concept_mastery,
       round(avg(a.score) FILTER (WHERE q.focus = 'figure'), 2)    AS figure_mastery,
       max(a.answered_at)                                          AS last_practiced_at
FROM answers a
JOIN questions q ON q.id = a.question_id
JOIN quizzes qz  ON qz.id = q.quiz_id
GROUP BY qz.student_id, qz.lesson_id;
