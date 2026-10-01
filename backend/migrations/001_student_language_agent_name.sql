-- Ngôn ngữ tương tác của từng học sinh (STT/TTS/câu trả lời); SGK vẫn là tiếng Việt
ALTER TABLE students
  ADD COLUMN language text NOT NULL DEFAULT 'vi' CHECK (language IN ('vi', 'ja'));

-- Agent thứ 7 cũng có thể trả lời học sinh (vd. "em đang yếu phần nào?")
ALTER TYPE agent_name ADD VALUE 'student_model';
