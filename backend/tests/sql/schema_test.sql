-- Kiểm tra ràng buộc của schema (backend/migrations). Chạy trong transaction rồi ROLLBACK → không để lại dữ liệu.
-- Tự chạy trong pytest (tests/test_schema_sql.py). Chạy tay:
-- docker exec -i lusia-postgres psql -U lusia -d lusia_db -v ON_ERROR_STOP=1 < backend/tests/sql/schema_test.sql
BEGIN;

CREATE FUNCTION pg_temp.must_fail(q text) RETURNS void AS $$
BEGIN
  EXECUTE q;
  RAISE EXCEPTION 'SHOULD HAVE FAILED: %', q;
EXCEPTION WHEN others THEN
  IF SQLERRM LIKE 'SHOULD HAVE FAILED%' THEN RAISE; END IF;
END $$ LANGUAGE plpgsql;

-- Dữ liệu mẫu theo kịch bản demo
INSERT INTO users (id, full_name, username, password_hash) VALUES
 ('00000000-0000-0000-0000-000000000001', 'Cô Lan', 'colan', 'x'),
 ('00000000-0000-0000-0000-000000000002', 'Em Minh', 'minh5a', 'x');
INSERT INTO teachers VALUES ('00000000-0000-0000-0000-000000000001');
INSERT INTO students (user_id, grade) VALUES ('00000000-0000-0000-0000-000000000002', 8);
INSERT INTO classes (id, teacher_id, name) VALUES ('00000000-0000-0000-0000-00000000000c', '00000000-0000-0000-0000-000000000001', '8A');
INSERT INTO class_students VALUES ('00000000-0000-0000-0000-00000000000c', '00000000-0000-0000-0000-000000000002');
INSERT INTO documents (id, kind, title, subject, grade, storage_key) VALUES
 ('00000000-0000-0000-0000-0000000000d1', 'textbook', 'Toán 8 tập 2', 'toan', 8, 'sgk/toan8-t2.pdf');
INSERT INTO lessons (id, document_id, position, title, page_start, page_end) VALUES
 ('00000000-0000-0000-0000-0000000000e1', '00000000-0000-0000-0000-0000000000d1', 1, 'Hàm số bậc nhất', 45, 50);
INSERT INTO chunks (document_id, lesson_id, page, kind, content, embedding, image_key, review) VALUES
 ('00000000-0000-0000-0000-0000000000d1', '00000000-0000-0000-0000-0000000000e1', 45, 'text', 'Hàm số y = ax + b (a ≠ 0)…', array_fill(0.1, ARRAY[1024])::vector, NULL, NULL),
 ('00000000-0000-0000-0000-0000000000d1', '00000000-0000-0000-0000-0000000000e1', 46, 'figure', 'Đồ thị y = 2x + 1 là đường thẳng…', array_fill(0.2, ARRAY[1024])::vector, 'fig/toan8-46.png', 'pending');
UPDATE chunks SET review = 'approved', reviewed_by = '00000000-0000-0000-0000-000000000001', reviewed_at = now() WHERE kind = 'figure';
INSERT INTO learning_sessions (id, student_id, lesson_id) VALUES
 ('00000000-0000-0000-0000-0000000000f1', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000e1');
INSERT INTO messages (session_id, role, agent, content) VALUES
 ('00000000-0000-0000-0000-0000000000f1', 'student', NULL, 'Giải thích đồ thị y = 2x + 1'),
 ('00000000-0000-0000-0000-0000000000f1', 'assistant', 'vision', 'Đây là một đường thẳng đi lên…');
INSERT INTO quizzes (id, student_id, lesson_id, session_id) VALUES
 ('00000000-0000-0000-0000-0000000000a1', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000e1', '00000000-0000-0000-0000-0000000000f1');
INSERT INTO questions (id, quiz_id, position, prompt, focus, choices, correct_answer, explanation) VALUES
 ('00000000-0000-0000-0000-0000000000b1', '00000000-0000-0000-0000-0000000000a1', 1, 'Đồ thị cắt trục tung tại?', 'figure', ARRAY['0','1','2'], '1', 'Thay x = 0'),
 ('00000000-0000-0000-0000-0000000000b2', '00000000-0000-0000-0000-0000000000a1', 2, 'Hệ số góc là gì?', 'concept', NULL, '2', 'a = 2');
INSERT INTO answers (question_id, answer_text, score, feedback) VALUES
 ('00000000-0000-0000-0000-0000000000b1', 'không', 0, 'Chưa đúng'),
 ('00000000-0000-0000-0000-0000000000b2', 'là số hai', 1, 'Đúng rồi');

DO $$
DECLARE m record;
BEGIN
  SELECT * INTO m FROM lesson_mastery;
  ASSERT m.mastery = 0.50 AND m.concept_mastery = 1.00 AND m.figure_mastery = 0.00, 'lesson_mastery sai';
  ASSERT (SELECT kind FROM chunks ORDER BY embedding <=> array_fill(0.2, ARRAY[1024])::vector LIMIT 1) IS NOT NULL, 'tìm kiếm vector lỗi';
END $$;

-- Những dữ liệu sai database phải từ chối
SELECT pg_temp.must_fail($$INSERT INTO users (full_name, username, password_hash) VALUES ('X', 'colan', 'x')$$);
SELECT pg_temp.must_fail($$INSERT INTO users (full_name, username, password_hash) VALUES ('X', 'Co Lan', 'x')$$);
SELECT pg_temp.must_fail($$UPDATE students SET grade = 13$$);
SELECT pg_temp.must_fail($$UPDATE students SET speech_rate = 3$$);
SELECT pg_temp.must_fail($$INSERT INTO classes (teacher_id, name) VALUES ('00000000-0000-0000-0000-000000000002', 'học sinh làm chủ lớp')$$);
SELECT pg_temp.must_fail($$INSERT INTO quizzes (student_id, lesson_id) VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000e1')$$);
SELECT pg_temp.must_fail($$INSERT INTO documents (kind, title, subject, grade, storage_key, uploaded_by) VALUES ('textbook', 'x', 'toan', 8, 'k1', '00000000-0000-0000-0000-000000000001')$$);
SELECT pg_temp.must_fail($$INSERT INTO documents (kind, title, subject, grade, storage_key) VALUES ('upload', 'x', 'toan', 8, 'k2')$$);
SELECT pg_temp.must_fail($$INSERT INTO lessons (document_id, position, title, page_start, page_end) VALUES ('00000000-0000-0000-0000-0000000000d1', 2, 'x', 10, 5)$$);
SELECT pg_temp.must_fail($$INSERT INTO chunks (document_id, page, kind, content, embedding) VALUES ('00000000-0000-0000-0000-0000000000d1', 1, 'figure', 'hình thiếu ảnh', array_fill(0.1, ARRAY[1024])::vector)$$);
SELECT pg_temp.must_fail($$INSERT INTO chunks (document_id, page, kind, content, embedding, review) VALUES ('00000000-0000-0000-0000-0000000000d1', 1, 'text', 'văn bản không cần duyệt', array_fill(0.1, ARRAY[1024])::vector, 'pending')$$);
SELECT pg_temp.must_fail($$UPDATE chunks SET reviewed_at = NULL WHERE kind = 'figure'$$);
SELECT pg_temp.must_fail($$INSERT INTO chunks (document_id, page, kind, content, embedding) VALUES ('00000000-0000-0000-0000-0000000000d1', 1, 'text', 'sai số chiều', array_fill(0.1, ARRAY[768])::vector)$$);
SELECT pg_temp.must_fail($$INSERT INTO messages (session_id, role, content) VALUES ('00000000-0000-0000-0000-0000000000f1', 'assistant', 'thiếu agent')$$);
SELECT pg_temp.must_fail($$INSERT INTO messages (session_id, role, agent, content) VALUES ('00000000-0000-0000-0000-0000000000f1', 'student', 'tutor', 'thừa agent')$$);
SELECT pg_temp.must_fail($$INSERT INTO questions (quiz_id, position, prompt, choices, correct_answer, explanation) VALUES ('00000000-0000-0000-0000-0000000000a1', 3, 'x', ARRAY['a','b'], 'c', 'x')$$);
SELECT pg_temp.must_fail($$INSERT INTO answers (question_id, answer_text, score, feedback) VALUES ('00000000-0000-0000-0000-0000000000b1', 'lần 2', 1, 'x')$$);
SELECT pg_temp.must_fail($$UPDATE answers SET score = 1.5$$);
SELECT pg_temp.must_fail($$UPDATE learning_sessions SET ended_at = started_at - interval '1 hour'$$);
SELECT pg_temp.must_fail($$DELETE FROM lessons$$);
SELECT pg_temp.must_fail($$DELETE FROM users WHERE id = '00000000-0000-0000-0000-000000000001'$$);

-- Xóa học sinh → xóa sạch dữ liệu học tập của em đó
DELETE FROM users WHERE id = '00000000-0000-0000-0000-000000000002';
DO $$ BEGIN
  ASSERT (SELECT count(*) FROM learning_sessions) + (SELECT count(*) FROM messages) + (SELECT count(*) FROM quizzes)
       + (SELECT count(*) FROM answers) + (SELECT count(*) FROM class_students) = 0, 'còn sót dữ liệu học sinh';
END $$;

\echo 'schema_test: OK'
ROLLBACK;
