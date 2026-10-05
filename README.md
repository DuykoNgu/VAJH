<div align="center">

# 🌟 LUSIA 🌟
## Hệ Thống AI Agent Hỗ Trợ Học Tập Cho Học Sinh Khiếm Thị
### *AI-Powered Learning Assistant for Visually Impaired Students*

**Voice-first • Multimodal • Agentic AI • RAG**

![Vietnam - Japan AI Hackathon 2026](https://img.shields.io/badge/Event-VJAH_2026-FF4500?style=for-the-badge)
![Team](https://img.shields.io/badge/Team-LUSIA_·_HUCE-007ACC?style=for-the-badge)
![Focus](https://img.shields.io/badge/Focus-Accessible_Education-2ea44f?style=for-the-badge)
![AI Architecture](https://img.shields.io/badge/AI-Multi--Agent_System-8A2BE2?style=for-the-badge)

---

👂 **L**isten • 🧠 **U**nderstand • 🤝 **S**hare • ✨ **I**nspire • 🛠️ **A**ssist  
*Lắng nghe • Thấu hiểu • Chia sẻ • Truyền cảm hứng • Hỗ trợ*

---

*“Công nghệ vì con người – Giáo dục không để ai bị bỏ lại phía sau”*  
*“Tri thức được lắng nghe – Không còn rào cản”*

*Dự án tham dự cuộc thi **Vietnam - Japan AI Hackathon 2026 (VJAH 2026)***

</div>

---

## 📖 Mục lục (Table of Contents)
- [✨ Giới thiệu đề tài (Project Overview)](#-giới-thiệu-đề-tài-project-overview)
- [💡 Ý nghĩa tên gọi LUSIA (The Philosophy of LUSIA)](#-ý-nghĩa-tên-gọi-lusia-the-philosophy-of-lusia)
- [🎯 Bối cảnh & Điểm đau thực tế (Context & Pain Points)](#-bối-cảnh--điểm-đau-thực-tế-context--pain-points)
- [👥 Đối tượng phục vụ (Target Users)](#-đối-tượng-phục-vụ-target-users)
- [🚀 Tính năng nổi bật & Hệ sinh thái Agent (Core Features)](#-tính-năng-nổi-bật--hệ-sinh-thái-agent-core-features)
- [🧩 Kiến trúc hệ thống (System Architecture)](#-kiến-trúc-hệ-thống-system-architecture)
- [🎬 Kịch bản sử dụng (Demo Scenario)](#-kịch-bản-sử-dụng-demo-scenario)
- [🛠️ Công nghệ & Ngăn xếp kỹ thuật (Tech Stack)](#️-công-nghệ--ngăn-xếp-kỹ-thuật-tech-stack)
- [📁 Cấu trúc thư mục (Project Structure)](#-cấu-trúc-thư-mục-project-structure)
- [🗄️ Cơ sở dữ liệu (Database Schema)](#️-cơ-sở-dữ-liệu-database-schema)
- [🛡️ Trí tuệ nhân tạo có trách nhiệm (Responsible AI)](#️-trí-tuệ-nhân-tạo-có-trách-nhiệm-responsible-ai)
- [📦 Hướng dẫn cài đặt & Khởi chạy (Getting Started)](#-hướng-dẫn-cài-đặt--khởi-chạy-getting-started)
  - [🚀 Lựa chọn 1: Triển khai toàn diện với Docker (Khuyên dùng)](#-lựa-chọn-1-triển-khai-toàn-diện-với-docker-khuyên-dùng)
  - [🛠️ Lựa chọn 2: Phát triển cục bộ kết hợp (Docker Infra + Local venv)](#️-lựa-chọn-2-phát-triển-cục-bộ-kết-hợp-docker-dịch-vụ-nền--local-python-venv)
- [🗺️ Lộ trình phát triển (Roadmap)](#️-lộ-trình-phát-triển-roadmap)
- [👥 Đội ngũ phát triển (Our Team)](#-đội-ngũ-phát-triển-our-team)

---

## ✨ Giới thiệu đề tài (Project Overview)

**LUSIA** là hệ sinh thái **AI Agent đa tác nhân (Multi-Agent System)** theo định hướng **Voice-first & Multimodal**, được thiết kế chuyên biệt nhằm đồng hành và hỗ trợ học tập cho **học sinh khiếm thị**.

Bằng việc kết hợp sức mạnh của **Generative AI, Retrieval-Augmented Generation (RAG)** và công nghệ thị giác máy tính đa phương thức, LUSIA mở ra cánh cửa tri thức bình đẳng, giúp học sinh khiếm thị có thể:
- Học tập hoàn toàn độc lập thông qua tương tác giọng nói hai chiều mà **không cần nhìn màn hình**.
- "Nhìn thấy" và hiểu trọn vẹn các biểu đồ, hình ảnh minh họa trong sách giáo khoa nhờ các tác nhân mô tả hình ảnh trực quan (Vision Agent).
- Tiếp cận kho học liệu sách giáo khoa chuẩn hóa được cá nhân hóa theo tốc độ tiếp thu của từng em.
- Kết nối chặt chẽ giữa học sinh và giáo viên thông qua bảng điều khiển theo dõi tiến độ học tập thông minh.

---

## 💡 Ý nghĩa tên gọi LUSIA (The Philosophy of LUSIA)

Đối với học sinh khiếm thị, đôi tai và trái tim là cầu nối lớn nhất tới thế giới tri thức. Từng chữ cái trong **LUSIA** là lời cam kết về một nền giáo dục hòa nhập:

| Ký tự | Từ khóa | Nghĩa Tiếng Việt | Vai trò trong hệ thống học tập cho học sinh khiếm thị |
| :---: | :--- | :--- | :--- |
| **L** | **Listen** | **Lắng nghe** | **Voice-first & Active Listening**: Lắng nghe mọi câu hỏi, phát âm, thắc mắc của học sinh bằng giọng nói tự nhiên thông qua hệ thống STT chuyên biệt. |
| **U** | **Understand** | **Thấu hiểu** | **Context & Visual Understanding**: Thấu hiểu nội dung học tập, "đọc vị" hình ảnh/đồ thị/sơ đồ bằng Vision Agent để chuyển hóa thành mô tả âm thanh trực quan, đồng thời thấu hiểu năng lực và điểm yếu của từng học sinh. |
| **S** | **Share** | **Chia sẻ** | **Knowledge Sharing (RAG)**: Truy xuất và chia sẻ kho tri thức sách giáo khoa, tài liệu học tập, giáo án chuẩn xác, truyền tải qua giọng đọc tự nhiên, truyền cảm. |
| **I** | **Inspire** | **Truyền cảm hứng** | **Empowerment & Motivation**: Đóng vai trò người bạn gia sư tận tâm, luôn kiên nhẫn khích lệ tinh thần, thắp sáng niềm tin và khát vọng chinh phục tri thức của các em. |
| **A** | **Assist** | **Hỗ trợ** | **Actionable Agent Support**: Tự động giải thích bài học, tạo bài luyện tập (Quiz), chấm điểm, hướng dẫn làm bài từng bước và hỗ trợ giáo viên theo dõi tiến độ can thiệp. |

---

## 🎯 Bối cảnh & Điểm đau thực tế (Context & Pain Points)

Giáo dục hòa nhập là một quyền cơ bản, nhưng đối với hàng triệu học sinh khiếm thị trên thế giới và tại Việt Nam, con đường tiếp cận tri thức vẫn đối mặt với những "điểm đau" (Pain Points) nhức nhối:

### 💥 1. Điểm đau của Học sinh khiếm thị (Students' Pain Points)
- 🚫 **"Bức tường" nội dung trực quan (The Visual Content Wall)**:
  - Sách giáo khoa và tài liệu học tập chứa đầy **hình vẽ sinh học, đồ thị toán học, sơ đồ vật lý, lược đồ địa lý**. Trình đọc màn hình thông thường hoàn toàn "bất lực" trước hình ảnh, biến các môn khoa học tự nhiên thành rào cản bất khả thi.
- 😔 **Mất quyền tự chủ & Phụ thuộc người khác (Loss of Autonomy)**:
  - Muốn học bài, giải bài tập hay ôn thi, các em luôn cần người thân hoặc bạn bè ngồi đọc hộ từng câu chữ. Điều này tạo tâm lý tự ti, mặc cảm và tước đi sự tự lập trong học tập.
- 📚 **Học liệu Braille khan hiếm, cồng kềnh và đắt đỏ**:
  - Một bộ SGK thông thường khi in nổi chữ Braille có thể dày gấp 4–5 lần, chi phí sản xuất đắt đỏ, mất hàng tháng để chuyển ngữ và rất khó cập nhật kịp chương trình giáo dục mới.
- 🐢 **Thiếu người đồng hành kiên nhẫn (Pacing & Empathy Deficit)**:
  - Trong lớp học hòa nhập, thầy cô giảng bài theo tốc độ chung. Học sinh khiếm thị không theo kịp nhưng ngại hỏi lại. Khi về nhà, các em thiếu một "gia sư" có thể kiên nhẫn giảng đi giảng lại nhiều lần bằng ngôn ngữ miêu tả dễ hiểu.

### 💥 2. Điểm đau của Giáo viên & Nhà trường (Teachers' Pain Points)
- ⏳ **Quá tải & Thiếu công cụ sư phạm chuyên biệt**:
  - Giáo viên lớp hòa nhập phải quản lý 30–40 học sinh, không đủ thời gian và kỹ năng để tự tay chuyển đổi giáo án, sơ đồ thành dạng mô tả âm thanh cho học sinh khiếm thị.
- 🔍 **Mất dấu tiến trình & "Điểm mù" trong đánh giá (Assessment Blind Spots)**:
  - Thầy cô rất khó biết chính xác học sinh khiếm thị đang bị hổng kiến thức ở khâu nào: do không hiểu bản chất bài học, hay do không hình dung được hình vẽ/biểu đồ minh họa.

### 💥 3. Hạn chế của Công nghệ hiện tại (Limitations of Existing Tech)
- **Screen Reader truyền thống (NVDA, TalkBack, VoiceOver)**: Giọng đọc cơ học, thiếu cảm xúc, không ngắt nghỉ sư phạm, không phân tích ngữ nghĩa hình ảnh và không thể tương tác hỏi - đáp hai chiều.
- **Chatbot AI thông thường**: Giao diện phụ thuộc vào việc nhìn màn hình và gõ phím; câu trả lời dài dòng không tối ưu cho thính giác; dễ xảy ra hiện tượng "ảo giác" (Hallucination) do không neo vào sách giáo khoa chuẩn.

---

### 💡 Bảng đối chiếu: Điểm đau ➡️ Giải pháp LUSIA (Pain-to-Solution Matrix)

| Điểm đau thực tế (Pain Point) | Thách thức cốt lõi | Giải pháp của **LUSIA** |
| :--- | :--- | :--- |
| **Không thể xem hình ảnh / đồ thị** | Trình đọc màn hình chỉ đọc văn bản, bỏ qua sơ đồ | **Vision Agent**: Tự động nhận diện, phân tích và "thuyết minh" đồ thị, hình ảnh bằng âm thanh trực quan. |
| **Phụ thuộc người đọc hộ** | Không tự chủ học bài, ôn thi lúc ở nhà | **Voice-first Two-way Dialog**: Tương tác đàm thoại 100% bằng giọng nói hai chiều, tự học độc lập. |
| **Học liệu Braille thiếu thốn** | Sách nổi in chậm, cồng kềnh, chi phí cao | **Document Agent + RAG**: Đọc hiểu SGK điện tử, OCR tức thì tài liệu PDF thành giọng đọc chuẩn. |
| **Hổng kiến thức, ngại hỏi** | Không có người kiên nhẫn giảng lại | **Learning/Tutor Agent**: Gia sư AI kiên nhẫn 24/7, giảng lại nhiều cách, gợi mở tư duy. |
| **Giáo viên quá tải, khó theo dõi** | Thiếu công cụ giám sát tiến độ học tập đặc thù | **Teacher Dashboard**: Tự động thống kê điểm nghẽn nhận thức, gợi ý can thiệp sư phạm kịp thời. |

---

> **Sứ mệnh của LUSIA:** Biến công nghệ AI thành "đôi mắt thứ hai" và "người bạn đồng hành tận tâm", giúp mọi học sinh khiếm thị tự tin làm chủ con đường học tập.

---

## 👥 Đối tượng phục vụ (Target Users)

### 1. 🎓 Học sinh khiếm thị (Visually Impaired Students)
- Học tập độc lập, chủ động tra cứu và nghe giảng giải mọi lúc mọi nơi.
- Tương tác hoàn toàn bằng giọng nói tự nhiên, không cần nhìn màn hình.
- Được hỗ trợ "đọc" hình ảnh, đồ thị, bảng biểu thông qua mô tả ngữ nghĩa chi tiết.

### 2. 👩‍🏫 Giáo viên & Nhà trường (Teachers & Educators)
- Hệ thống **Teacher Dashboard** hỗ trợ theo dõi tiến trình học tập, thống kê các chủ đề học sinh gặp khó khăn.
- Gợi ý phương pháp và thời điểm can thiệp sư phạm kịp thời, đồng hành cùng học sinh hiệu quả hơn.

---

## 🚀 Tính năng nổi bật & Hệ sinh thái Agent (Core Features)

Hệ thống được vận hành bởi kiến trúc **Multi-Agent (Đa tác nhân)** chuyên trách:

### 1. Tầng trợ năng & tương tác không nhìn (Accessibility Layer)
- **Speech-to-Text (STT)**: Chuyển đổi giọng nói học sinh thành văn bản với độ trễ thấp, hỗ trợ tiếng Việt và tiếng Nhật.
- **Text-to-Speech (TTS)**: Giọng đọc truyền cảm, tốc độ tùy biến, phát âm chuẩn xác thuật ngữ khoa học và SGK.
- **Voice Command & Non-visual UI**: Điều hướng toàn bộ ứng dụng chỉ bằng khẩu lệnh và cử chỉ âm thanh, tương thích hoàn hảo với Screen Reader.

### 2. Hệ thống Tác nhân thông minh (AI Agent Core)
- 🎯 **Orchestrator Agent**: "Nhạc trưởng" tiếp nhận yêu cầu, phân tích ý định, lập kế hoạch và điều phối các agent chuyên biệt.
- 📖 **Learning / Tutor Agent**: Giảng giải bài học theo phương pháp gợi mở, giải thích lại nhiều lần bằng ví dụ gần gũi, cá nhân hóa theo trình độ.
- 📚 **RAG / Knowledge Agent**: Truy xuất chính xác nội dung sách giáo khoa, bài tập và giáo án chuẩn từ cơ sở tri thức đã kiểm chứng.
- 👁️ **Vision Agent**: Đọc hiểu và chuyển đổi hình ảnh, đồ thị hàm số, bản đồ địa lý, sơ đồ sinh học thành các đoạn mô tả chi tiết bằng âm thanh.
- 📄 **Document Agent**: OCR tài liệu học tập, đọc file PDF, tóm tắt các bài học dài thành các ý trọng tâm dễ nhớ.
- 📝 **Assessment Agent**: Tự động sinh câu hỏi trắc nghiệm/tự luận bằng giọng nói, chấm bài tức thì và giải thích cặn kẽ đáp án.
- 🧠 **Student Model & Memory**: Ghi nhớ lịch sử học tập, môn học, phân tích điểm mạnh, điểm yếu và sở thích của từng em để tối ưu lộ trình.

### 3. Cổng thông tin cho giáo viên (Teacher Dashboard)
- Giám sát tiến độ học tập theo thời gian thực.
- Cảnh báo sớm các lỗ hổng kiến thức để giáo viên hỗ trợ kịp thời.

---

## 🧩 Kiến trúc hệ thống (System Architecture)

```mermaid
flowchart TB
    subgraph USERS["👥 Người dùng"]
        direction TB
        HS["🎓 Học sinh khiếm thị"]
        GV["👩‍🏫 Giáo viên"]
        CH["Kênh tương tác<br/>🎤 Giọng nói · 📝 Văn bản · 📷 Hình ảnh · 📄 PDF"]
    end

    subgraph ACC["♿ Accessibility Layer"]
        direction TB
        STT["Speech-to-Text"]
        TTS["Text-to-Speech"]
        VC["Voice Command"]
        SR["UI thân thiện Screen Reader"]
    end

    subgraph APP["🌐 API / Application Layer"]
        direction LR
        FE["Frontend Web / Mobile<br/>Next.js + Tailwind CSS"] --> BE["FastAPI Backend / API Gateway<br/>phiên làm việc · xác thực"]
    end

    subgraph CORE["🧠 AI Agent Core (Multi-Agent System)"]
        direction TB
        ORC{{"Orchestrator Agent<br/>hiểu yêu cầu · lập kế hoạch<br/>chọn agent / tool · theo dõi trạng thái"}}
        ORC <--> TUT["📖 Learning / Tutor"] & RAG["📚 RAG / Knowledge"] & VIS["👁️ Vision"] & DOC["📄 Document"] & ASM["📝 Assessment"] & STM["🧠 Student Model / Memory"]
    end

    subgraph TOOLS["🔧 Tool Layer"]
        direction TB
        T1["search_knowledge()<br/>read_document()<br/>describe_image()"]
        T2["get_student_profile()<br/>save_learning_result()<br/>create_learning_plan()"]
        T3["generate_quiz()<br/>grade_answer()<br/>send_teacher_report()"]
    end

    subgraph DATA["🗄️ Data / Storage Layer"]
        direction TB
        PG[("PostgreSQL + pgvector (Neon)<br/>người dùng, tiến độ, điểm<br/>embedding SGK cho RAG")]
        RD[("Redis<br/>session, cache")]
        S3[("MinIO / S3<br/>PDF, ảnh, audio")]
    end

    subgraph OUT["📤 Đầu ra / Quản trị"]
        direction TB
        RES["🔊 Phản hồi cho học sinh<br/>giọng nói · mô tả hình ảnh · bài học cá nhân hóa"]
        TD["📊 Teacher Dashboard<br/>tiến độ · điểm yếu · gợi ý can thiệp"]
    end

    USERS --> ACC --> APP --> CORE --> TOOLS --> DATA
    CORE --> OUT
```

**Luồng hoạt động chính:**

```mermaid
flowchart LR
    A["🎤 Giọng nói<br/>học sinh"] --> B["STT"] --> C{{"Orchestrator"}} --> D["RAG /<br/>Learning Agent"] --> E["Đánh giá<br/>câu trả lời"] --> F[("Cập nhật<br/>hồ sơ học tập")] --> G["🔊 TTS<br/>phản hồi"]
```

> 🖼️ Bản thiết kế đồ họa đầy đủ: [docs/architecture.webp](docs/architecture.webp)

---

## 🎬 Kịch bản sử dụng (Demo Scenario)

> 🎓 *"LUSIA ơi, giải thích giúp mình đồ thị trong bài Hàm số bậc nhất, sách Toán 8."*  
> 🤖 **Knowledge Agent** tìm đúng bài trong SGK → **Vision Agent** mô tả: *"Đây là đồ thị hàm số y = 2x + 1: một đường thẳng đi lên từ trái sang phải, cắt trục tung tại điểm có tung độ bằng 1…"*  
> 🎓 *"Vì sao nó cắt trục tung ở 1?"*  
> 🤖 **Tutor Agent** gợi mở: *"Em thử thay x = 0 vào công thức xem y bằng bao nhiêu nhé?"*  
> 📝 Cuối buổi, **Assessment Agent** hỏi 3 câu trắc nghiệm bằng giọng nói; kết quả được ghi vào Student Model và hiển thị trên **Teacher Dashboard**.

---

### ▶️ Chạy demo (MVP)

Trên một laptop, dùng **Google Chrome** (nhận giọng nói tiếng Việt qua Web Speech API; cần Internet).

#### 🚀 Cách 1: Chạy nhanh bằng Docker (Toàn bộ Backend trong Container)

```bash
# 1. Khởi chạy trọn bộ backend stack (Postgres + pgvector, Redis, Migrate, FastAPI, Arq Worker)
docker compose --profile app up -d --build

# 2. Khởi tạo tài khoản & lớp học mẫu (giáo viên colan, học sinh minh8a, hana8a)
docker compose --profile app exec api python -m app.seed

# 3. Tải model giọng đọc ZeroTTS (~900 MB) và model bố cục DocLayout-YOLO (~40 MB) (chỉ cần chạy một lần)
docker compose --profile app exec api python -m app.voice.tts --download
docker compose --profile app exec api python -c "from huggingface_hub import hf_hub_download as d; d('juliozhao/DocLayout-YOLO-DocStructBench', 'doclayout_yolo_docstructbench_imgsz1024.pt', local_dir='data/models/doclayout')"

# 4. Nạp SGK: Tải trực tiếp qua Web UI tại http://localhost:3000/curation hoặc dùng CLI với file mẫu:
docker cp "SGK Toán 8, tập một-mau.pdf" $(docker compose ps -q api):/app/data/files/toan8.pdf
docker compose --profile app exec api python -m app.ingest /app/data/files/toan8.pdf --title "Toán 8 tập 1" --subject toan --grade 8

# 5. Khởi chạy giao diện Frontend
cd frontend && npm install && npm run dev              # Mở http://localhost:3000/learn
```

#### 🛠️ Cách 2: Chạy kết hợp (Docker Dịch vụ nền + Local Python venv)

```bash
docker compose up -d                                   # Chỉ bật Postgres + Redis
cd backend && source .venv/bin/activate
python -m app.migrate && python -m app.seed            # Schema + tài khoản demo
python -m app.voice.tts --download                     # Model giọng đọc ZeroTTS (~900 MB, một lần)
python -c "from huggingface_hub import hf_hub_download as d; d('juliozhao/DocLayout-YOLO-DocStructBench', 'doclayout_yolo_docstructbench_imgsz1024.pt', local_dir='data/models/doclayout')"  # Model bố cục tìm hình (~40 MB)
python -m app.ingest ~/Downloads/toan8.pdf --title "Toán 8 tập 2" --subject toan --grade 8
python -m app.outline <document_id>                    # Sách nạp trước khi có dàn ý: rút dàn ý giảng (~6 s / bài)
arq app.worker.WorkerSettings &                        # Worker xử lý PDF nền
uvicorn app.main:app --port 8000                       # Đợi nạp model giọng đọc & embedding
cd ../frontend && npm run dev                          # Mở http://localhost:3000/learn
```

> Nếu cổng 3000 đang bận, Next.js chạy ở 3001: thêm cổng đó cho backend bằng `FRONTEND_ORIGINS="http://localhost:3000,http://localhost:3001"`.

**Lời thoại demo.** Bước 0 — giáo viên chuẩn bị tri thức trên `/curation`: tải PDF lên (hoặc mở sách đã nạp), sửa đoạn văn lỗi, kiểm tra dữ kiện từng hình rồi **Duyệt**, xem **dàn ý giảng** của từng bài (các ý chính rút từ sách, kèm câu hỏi kiểm tra và đáp án — sửa nếu cần), bấm **Nghe thử** một ý, và **Xuất bản**. Học sinh chỉ thấy tài liệu đã xuất bản; tri thức là cơ sở cố định, còn cách LUSIA diễn đạt thay đổi mỗi lần giảng.

Học sinh (không cần nhìn màn hình, không cần tìm nút nào):

1. Mở `/learn`, nhấn **phím bất kỳ** → LUSIA chào và đọc danh sách bài.
2. Giữ **phím cách**, nói *“bài hai”* (hoặc mũi tên xuống + Enter) → LUSIA **giảng ngay phần 1** rồi hỏi một câu kiểm tra.
3. Trả lời bằng giọng nói → LUSIA chấm (đúng / đúng một phần / chưa đúng, giảng lại nếu cần) → nói *“tiếp”*.
4. Phần có hình: **Vision** lấy dữ kiện hình đã duyệt, Tutor dựng hình trong đầu em bằng tưởng tượng, rồi hỏi tiếp. Màn hình hiện **Orchestrator → Vision → Tutor → Assessment**.
5. Hỏi chen bất cứ lúc nào: *“Trục tung là trục nào?”* → LUSIA trả lời rồi nhắc lại câu hỏi đang chờ.
6. Hết bài: LUSIA tóm tắt và mời *“kiểm tra mình”* → 3 câu trắc nghiệm bằng giọng nói → điểm.
7. Mở `/dashboard`: lớp 8A hiện **Hiểu bài / Hiểu hình** (gồm cả câu kiểm tra từng phần) và chỗ **Yếu**.

**Giám sát và debug** (`/monitor`): mỗi lượt học, vào bài, nghe thử và nạp sách là một *trace*: agent nào chạy, lượt gọi LLM nào (route, model, effort, thời gian, token, prompt và câu trả lời), lỗi ở đâu. Trang tổng hợp p50/p95 theo agent và route, tỉ lệ câu “không có trong SGK”, điểm trung bình câu kiểm tra, 👍/👎 kèm ghi chú cho từng trace. Mỗi câu trả lời cho học sinh có `trace_id` để tra lại. Ước tính chi phí: đặt `LLM_PRICE_IN_PER_M` và `LLM_PRICE_OUT_PER_M` (USD / 1 triệu token) trong `backend/.env`. Xem trace dạng **JSON lồng nhau** (lượt gọi LLM nằm trong `children` của agent), sao chép hoặc tải `trace-<id>.json`. Nội dung prompt chỉ lưu đủ cho lượt lỗi / bị từ chối và một mẫu ngẫu nhiên (`TRACE_PAYLOADS=sampled`, `TRACE_SAMPLE_RATE=0.25`; debug kỹ thì đặt `TRACE_PAYLOADS=all`); worker tự xoá nội dung sau `TRACE_PAYLOAD_DAYS=7` ngày (trừ trace đã đánh giá) và xoá trace sau `TRACE_KEEP_DAYS=90` ngày, chạy lúc 03:00.

Phím ở mọi nơi: **Space** giữ để nói · **Esc** dừng · **R** nghe lại · **H** trợ giúp. Lệnh nói: *nhắc lại, dừng, đổi bài, chậm lại, nhanh lên, trợ giúp, tiếp, kiểm tra mình*.

> Máy có ứng dụng khác chiếm cổng 8000/3000? Chạy API ở cổng khác (`uvicorn app.main:app --port 8010`) và frontend với `NEXT_PUBLIC_API_URL=http://localhost:8010 npm run dev -- --port 3001`, thêm `FRONTEND_ORIGINS="http://localhost:3001"` cho backend.

Đặt lại dữ liệu demo giữa các lần tập (xóa kết quả quiz, đưa hình về chờ duyệt, tài liệu về bản nháp):

```bash
docker exec -i lusia-postgres psql -U lusia -d lusia_db -c "DELETE FROM learning_sessions; DELETE FROM quizzes;" \
  -c "UPDATE chunks SET review='pending', reviewed_by=NULL, reviewed_at=NULL WHERE kind='figure';" \
  -c "UPDATE documents SET published_at=NULL, published_by=NULL;"
```

---

## 🛠️ Công nghệ & Ngăn xếp kỹ thuật (Tech Stack)

- **AI & Multi-Agent Core**: LLM (Gemini, Claude, GPT), Agent Frameworks (LangChain, LangGraph), RAG Pipeline.
- **Voice & Accessibility**: Whisper / WhisperX (Speech-to-Text), Neural TTS (Việt - Nhật), Web Speech API.
- **Vision & Document Processing**: Multimodal Vision LLM, OCR (Tesseract / PaddleOCR / Surya), PDF Parsers.
- **Backend & API Gateway**: Python **FastAPI** (Uvicorn).
- **Frontend**: **Next.js** (App Router, TypeScript) + **Tailwind CSS** — Responsive Web & Mobile, High Contrast, Screen Reader Friendly (WAI-ARIA).
- **Cơ sở dữ liệu & Lưu trữ (Data & Storage)**:
  - **PostgreSQL + pgvector** (chạy trên **Neon**): Hồ sơ học sinh, giáo viên, tiến độ học **và** embedding SGK cho RAG — một database duy nhất.
  - **In-Memory Cache**: Redis (Quản lý phiên đàm thoại, trạng thái ngắn hạn của Agent).
  - **Object Storage**: MinIO / AWS S3 (Lưu trữ file âm thanh, tài liệu PDF, hình ảnh bài học).

---

## 📁 Cấu trúc thư mục (Project Structure)

Mỗi thư mục tương ứng một tầng trong [sơ đồ kiến trúc](#-kiến-trúc-hệ-thống-system-architecture):

```text
Hackathon_VJAI/
├── frontend/                  # Next.js (App Router) + Tailwind CSS
│   └── src/app/
│       ├── layout.tsx         # Layout chung (lang="vi" cho trình đọc màn hình)
│       ├── page.tsx           # Trang chủ: chọn Học sinh / Giáo viên
│       ├── learn/             # Giao diện học sinh (voice-first)
│       ├── curation/          # Kiểm duyệt nội dung (chuẩn bị tri thức, xuất bản)
│       ├── monitor/           # Giám sát agent + LLM (trace, độ trễ, token, đánh giá)
│       └── dashboard/         # Teacher Dashboard
├── backend/                   # Python FastAPI
│   ├── app/
│   │   ├── main.py            # API / Application Layer: khởi tạo app, CORS, router
│   │   ├── api/               # Endpoint: chat.py (học sinh), teacher.py (giáo viên)
│   │   ├── voice/             # Accessibility Layer: stt.py, tts.py
│   │   ├── agents/            # AI Agent Core: orchestrator, tutor, knowledge,
│   │   │                      #   vision, document, assessment, student_model
│   │   ├── tools.py           # Tool Layer: search_knowledge(), generate_quiz(), …
│   │   └── storage/           # Data Layer: vector (pgvector), relational (PostgreSQL),
│   │       │                  #   cache (Redis), files (MinIO / S3)
│   ├── migrations/            # Schema database: 000_init.sql, 001_…sql (python -m app.migrate)
│   ├── tests/                 # pytest (+ sql/schema_test.sql kiểm tra ràng buộc)
│   ├── requirements.txt
│   └── .env.example
├── docker-compose.yml         # Cấu hình Docker: Dịch vụ nền (Postgres, Redis) & Profile "app" (Migrate, API, Worker)
└── docs/
    └── architecture.webp      # Sơ đồ kiến trúc hệ thống
```

---

## 🗄️ Cơ sở dữ liệu (Database Schema)

Một database **PostgreSQL + pgvector** (chạy trên **Neon**, hoặc Docker khi làm offline) chứa cả dữ liệu học tập lẫn embedding cho RAG; file gốc (PDF, ảnh) nằm ở MinIO / S3. Chi tiết: [`backend/migrations/`](backend/migrations/).

```mermaid
erDiagram
    users ||--o| students : "là"
    users ||--o| teachers : "là"
    teachers ||--o{ classes : "phụ trách"
    classes ||--o{ class_students : "gồm"
    students ||--o{ class_students : "thuộc"
    users |o--o{ documents : "tải lên"
    documents ||--o{ lessons : "gồm"
    documents ||--o{ chunks : "cắt thành"
    lessons |o--o{ chunks : "chứa"
    teachers |o--o{ chunks : "duyệt mô tả hình"
    students ||--o{ learning_sessions : "học"
    lessons |o--o{ learning_sessions : "về"
    learning_sessions ||--o{ messages : "gồm"
    students ||--o{ quizzes : "làm"
    lessons ||--o{ quizzes : "về"
    quizzes ||--o{ questions : "gồm"
    questions ||--o| answers : "được trả lời"
```

| Nhóm | Bảng | Ghi chú |
| :--- | :--- | :--- |
| Người dùng | `users`, `students`, `teachers`, `classes`, `class_students` | **Hiện chưa có đăng nhập** (danh tính dev, xem Getting Started); giai đoạn 12 thêm đăng nhập: học sinh `username` + mã PIN 6 số do giáo viên cấp (**đọc bằng giọng nói** hoặc nhờ người khác gõ hộ), giáo viên dùng mật khẩu. Vai trò = có dòng trong `students` / `teachers`, nên database tự chặn gán nhầm vai trò. |
| Học liệu & RAG | `documents`, `lessons`, `chunks` | `chunks` chứa đoạn SGK và **mô tả hình** do Vision Agent viết, kèm embedding (`vector(1024)`, model `AITeamVN/Vietnamese_Embedding_v2`). Mô tả hình phải được **giáo viên duyệt** (Human Oversight). |
| Hội thoại | `learning_sessions`, `messages` | Chỉ lưu transcript, **không lưu audio gốc** (bảo vệ quyền riêng tư của trẻ). Mỗi câu trả lời ghi rõ agent nào trả lời. |
| Đánh giá | `quizzes`, `questions`, `answers` | Điểm từ 0–1 (tự luận chấm từng phần). Mỗi câu hỏi đánh dấu `focus`: về **kiến thức** hay về **hình vẽ**. |
| Student Model | view `lesson_mastery` | Mức nắm bài theo từng bài, tách `concept_mastery` / `figure_mastery` → giáo viên biết học sinh hổng vì không hiểu bài hay vì không hình dung được hình. |

Hai truy vấn cốt lõi:

```sql
-- Knowledge Agent: tìm 5 đoạn liên quan, chỉ dùng mô tả hình đã được giáo viên duyệt
SELECT content FROM chunks
WHERE lesson_id = $1 AND (kind = 'text' OR review = 'approved')
ORDER BY embedding <=> $2
LIMIT 5;

-- Teacher Dashboard: học sinh nào đang yếu bài nào, yếu phần nào
SELECT u.full_name, l.title, m.concept_mastery, m.figure_mastery
FROM class_students cs
JOIN lesson_mastery m ON m.student_id = cs.student_id
JOIN users u   ON u.id = cs.student_id
JOIN lessons l ON l.id = m.lesson_id
WHERE cs.class_id = $1 AND m.mastery < 0.5;
```

---

## 🛡️ Trí tuệ nhân tạo có trách nhiệm (Responsible AI)

- 🔒 **Privacy (Bảo mật quyền riêng tư)**: Dữ liệu giọng nói và thông tin học tập của học sinh được bảo vệ tuyệt đối theo chuẩn an toàn.
- 🛡️ **Safety & Content Moderation**: Lọc bỏ các nội dung không phù hợp lứa tuổi học đường.
- ♿ **Accessibility (Chuẩn trợ năng quốc tế)**: Tuân thủ các tiêu chuẩn WCAG 2.1 AA/AAA về khả năng tiếp cận cho người khiếm thị.
- 🎯 **Hallucination Control**: Kiểm soát hiện tượng ảo giác của AI thông qua RAG đối chiếu trực tiếp với Sách giáo khoa chính thống.
- 👥 **Human Oversight**: Luôn có sự giám sát và đồng hành của giáo viên trong suốt quá trình học tập.

---

## 📦 Hướng dẫn cài đặt & Khởi chạy (Getting Started)

> ℹ️ Khung dự án (frontend + backend) đã được khởi tạo hoàn chỉnh; các agent và pipeline RAG/Voice/Vision đang được hoàn thiện trong khuôn khổ VJAH 2026.

Dự án hỗ trợ **2 phương thức triển khai chính**:
1. **🚀 Lựa chọn 1: Triển khai toàn diện với Docker (Khuyên dùng)** — Toàn bộ dịch vụ backend, cơ sở dữ liệu, hàng đợi và worker chạy trong container Docker chỉ với một lệnh. Không cần cấu hình môi trường Python trên máy host.
2. **🛠️ Lựa chọn 2: Phát triển cục bộ kết hợp (Docker Dịch vụ nền + Local Python venv)** — Docker chạy PostgreSQL + Redis, backend chạy trực tiếp qua `virtualenv`. Phù hợp cho lập trình viên muốn debug sâu và tận dụng Apple Vision OCR bản địa trên macOS.

---

### 1. Yêu cầu tiên quyết (Prerequisites)

- **Docker & Docker Compose** (v2 trở lên): Cài đặt [Docker Desktop](https://www.docker.com/products/docker-desktop/) (macOS / Windows / Linux) hoặc [OrbStack](https://orbstack.dev/) (macOS).
- **Node.js** >= 20.9 (để chạy giao diện Web Next.js).
- **Python** >= 3.10 (chỉ cần nếu bạn chọn *Lựa chọn 2* để chạy backend trên máy host).
- **OpenAI API Key**: Cần có API Key (hỗ trợ các model như `gpt-4o`, `gpt-4o-mini`) để các Agent suy luận và trả lời.
- **Trình duyệt Google Chrome**: Hỗ trợ chuẩn Web Speech API (nhận diện giọng nói tiếng Việt với độ trễ thấp).
- **Thiết bị**: Micro & Loa hoạt động tốt để giao tiếp bằng giọng nói hai chiều.

---

### 2. Tải mã nguồn & Cấu hình môi trường (`.env`)

```bash
git clone https://github.com/DatTQ27/Hackathon_VJAI.git
cd Hackathon_VJAI
cp backend/.env.example backend/.env
```

Mở file `backend/.env` và cập nhật các khóa API quan trọng:
```ini
# Khóa API để kích hoạt các Agent LLM
OPENAI_API_KEY="sk-..."
OPENAI_LLM_MODEL="gpt-4o-mini"   # hoặc gpt-4o, gpt-4o-mini
```

> 💡 **Lưu ý đặc biệt cho Docker:**  
> File `docker-compose.yml` đã được cấu hình sẵn mạng nội bộ `lusia-network`: biến `DATABASE_URL` tự động trỏ đến `postgresql://lusia:lusia@postgres:5432/lusia_db` và `REDIS_URL` tự động trỏ đến `redis://redis:6379`. Bạn **không cần thay đổi** chuỗi kết nối database trong file `backend/.env` khi triển khai bằng Docker!

---

### 3. Khởi chạy Backend & Hạ tầng

Chọn **1 trong 2** phương án dưới đây tùy thuộc vào nhu cầu của bạn:

#### 🚀 Lựa chọn 1: Triển khai toàn diện với Docker (Khuyên dùng)

Phương thức này đóng gói toàn bộ hệ sinh thái backend vào các container Docker độc lập, đảm bảo môi trường đồng nhất và khởi chạy tức thì chỉ với một lệnh duy nhất.

##### Sơ đồ các dịch vụ trong Docker Compose

```
           [ Next.js Frontend ] (Cổng 3000 trên máy Host)
                     │
                     ▼
           [ FastAPI API Container ] (Cổng 8000)
             ├── Mount: ./backend/app (Hot-reload code)
             ├── Mount: ./backend/data/models (Lưu trữ model TTS & Vision)
             └── Profile: "app"
                     │
     ┌───────────────┼───────────────┬────────────────┐
     ▼               ▼               ▼                ▼
[ Postgres 16 ]  [ Redis 7 ]   [ Migrate ]      [ Worker ]
  + pgvector       Cache &      Tự động chạy     Arq background job:
  Cổng 5432       Queue 6379   python -m        xử lý PDF, OCR,
                               app.migrate      trích xuất hình
```

| Tên Dịch Vụ | Tên Container | Cổng Host | Chức năng & Ghi chú |
| :--- | :--- | :--- | :--- |
| `postgres` | `lusia-postgres` | `5432` | PostgreSQL 16 tích hợp `pgvector`: Lưu trữ hồ sơ người dùng, tiến độ học tập và vector embedding SGK cho RAG. Tự động kiểm tra sức khỏe (`healthcheck`). |
| `redis` | `lusia-redis` | `6379` | In-memory cache lưu phiên hội thoại học sinh và hàng đợi tác vụ nền (`arq`). |
| `migrate` | *(chạy xong tự thoát)* | - | Khởi chạy một lần sau khi PostgreSQL sẵn sàng để tự động tạo/cập nhật cấu trúc bảng (`python -m app.migrate`). |
| `api` | `hackathon_vjai-api-1` | `8000` | FastAPI server. Tự động tải lại khi chỉnh sửa code trong `backend/app`. |
| `worker` | `hackathon_vjai-worker-1` | - | Background worker (`arq`) xử lý phân tích PDF, OCR sách scan, nhận diện hình ảnh và tạo embedding. |

##### Bước 1: Khởi động hệ thống Backend bằng Docker Compose

Chạy lệnh với profile `app` để kích hoạt cả hạ tầng và ứng dụng:

```bash
docker compose --profile app up -d --build
```

Kiểm tra trạng thái các container đang chạy:
```bash
docker compose ps
```
*(Đảm bảo cả `lusia-postgres`, `lusia-redis`, container `api` và `worker` đều đang ở trạng thái `Up`)*.

##### Bước 2: Khởi tạo dữ liệu người dùng mẫu (Seed Data)

> ⚠️ **Quan trọng:** Tiến trình `migrate` chỉ tạo khung cơ sở dữ liệu. Để đăng nhập và thử nghiệm các tính năng, bạn cần khởi tạo dữ liệu ban đầu (giáo viên `colan`, lớp `8A`, học sinh `minh8a` và `hana8a`):

```bash
docker compose --profile app exec api python -m app.seed
```

Kiểm tra nhanh kết nối API và danh tính dev:
```bash
curl -s http://localhost:8000/health/ready     # {"status":"ready","database":"ok","redis":"ok"}
curl -s http://localhost:8000/me               # Trả về thông tin học sinh mặc định minh8a (tiếng Việt)
```

##### Bước 3: Tải các model AI chạy cục bộ (ZeroTTS & DocLayout-YOLO)

Hệ thống sử dụng model TTS tiếng Việt tự nhiên và model thị giác để phân tích tài liệu:

```bash
# 1. Tải model giọng đọc tiếng Việt ZeroTTS (~900 MB, chỉ cần tải một lần):
docker compose --profile app exec api python -m app.voice.tts --download

# 2. Tải model nhận diện cấu trúc & hình vẽ DocLayout-YOLO (~40 MB, chỉ cần tải một lần):
docker compose --profile app exec api python -c "from huggingface_hub import hf_hub_download as d; d('juliozhao/DocLayout-YOLO-DocStructBench', 'doclayout_yolo_docstructbench_imgsz1024.pt', local_dir='data/models/doclayout')"
```

> 💾 **Cơ chế lưu trữ Model:** Các model được lưu trữ tại `backend/data/models/` trên máy host (được mount trực tiếp vào container) và thư mục cache HuggingFace (`hf_cache` volume). Sau khi tải một lần, bạn có thể khởi động lại container hoặc rebuild image mà không cần tải lại.

##### Bước 4: Nạp Sách giáo khoa & Tài liệu học tập (Ingestion)

Bạn có thể nạp tài liệu vào hệ thống theo một trong hai cách:

- **Cách 1 (Giao diện Web - Trực quan, khuyên dùng):**
  Sau khi khởi chạy Frontend (Bước 4), truy cập trang Kiểm duyệt: <http://localhost:3000/curation>, chọn tệp PDF và bấm nạp. Tác vụ sẽ được đẩy vào Redis và Background Worker trong Docker sẽ xử lý tự động.
- **Cách 2 (Dòng lệnh CLI với file mẫu có sẵn trong repo):**
  Dự án đi kèm file SGK mẫu `SGK Toán 8, tập một-mau.pdf`. Bạn có thể nạp trực tiếp qua Docker:
  ```bash
  # Sao chép file PDF mẫu vào thư mục dữ liệu của container:
  docker cp "SGK Toán 8, tập một-mau.pdf" $(docker compose ps -q api):/app/data/files/toan8.pdf

  # Chạy lệnh nạp tài liệu trực tiếp bên trong container:
  docker compose --profile app exec api python -m app.ingest /app/data/files/toan8.pdf --title "Toán 8 tập 1" --subject toan --grade 8
  ```

##### 📋 Bảng tra cứu lệnh Docker thường dùng

| Thao tác | Lệnh Docker |
| :--- | :--- |
| **Xem logs thời gian thực của API** | `docker compose logs -f api` |
| **Xem logs của Background Worker** | `docker compose logs -f worker` |
| **Kiểm tra trạng thái các service** | `docker compose ps` |
| **Mở bash shell trong container API** | `docker compose --profile app exec api bash` |
| **Truy cập dòng lệnh PostgreSQL (`psql`)** | `docker exec -it lusia-postgres psql -U lusia -d lusia_db` |
| **Khởi động lại API và Worker** | `docker compose --profile app restart api worker` |
| **Tạm dừng hệ thống (giữ nguyên dữ liệu)** | `docker compose --profile app stop` |
| **Dừng và gỡ container** | `docker compose --profile app down` |
| **Xóa sạch container và toàn bộ volumes dữ liệu** | `docker compose --profile app down -v` |
| **Đặt lại (reset) dữ liệu demo học tập** | `docker exec -i lusia-postgres psql -U lusia -d lusia_db -c "DELETE FROM learning_sessions; DELETE FROM quizzes;" -c "UPDATE chunks SET review='pending', reviewed_by=NULL, reviewed_at=NULL WHERE kind='figure';" -c "UPDATE documents SET published_at=NULL, published_by=NULL;"` |

---

#### 🛠️ Lựa chọn 2: Phát triển cục bộ kết hợp (Docker Dịch vụ nền + Local Python venv)

Phương thức này dành cho các nhà phát triển muốn can thiệp sâu vào backend Python, chạy test với pytest hoặc tối ưu hiệu năng OCR trên macOS:

> 🍎 **Lợi thế trên macOS:** Chạy local venv cho phép kích hoạt `local_ocr` sử dụng native Apple Vision framework (`pyobjc-framework-Vision`). Nhờ đó, việc nhận diện chữ trên sách scan được thực hiện trực tiếp trên chip Apple Silicon cực nhanh, tiết kiệm hơn 7 lần token LLM so với việc gửi ảnh lên cloud.

#### 1. Khởi chạy Dịch vụ nền (Postgres + pgvector & Redis)

Chỉ bật 2 dịch vụ nền mà không bật profile `app`:

```bash
docker compose up -d          # Khởi chạy lusia-postgres (5432) và lusia-redis (6379)
```

*(Tùy chọn: Nếu dùng Neon Cloud Database, chạy `cd backend && neon link && cd ..` để ghi URL Neon vào `.env`)*.

#### 2. Cài đặt môi trường Python & Khởi chạy Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate      # Trên Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

# Cập nhật schema database và nạp dữ liệu demo:
python -m app.migrate          # Áp dụng các migration SQL
python -m app.seed             # Tạo tài khoản colan, minh8a, hana8a

# Tải model AI cục bộ:
python -m app.voice.tts --download
python -c "from huggingface_hub import hf_hub_download as d; d('juliozhao/DocLayout-YOLO-DocStructBench', 'doclayout_yolo_docstructbench_imgsz1024.pt', local_dir='data/models/doclayout')"

# Nạp sách giáo khoa (CLI):
python -m app.ingest ~/Downloads/toan8.pdf --title "Toán 8 tập 2" --subject toan --grade 8
# Sách nạp trước khi có dàn ý giảng: rút dàn ý (một lượt LLM / bài)
python -m app.outline <document_id>

# Khởi chạy Background Worker (chạy nền):
arq app.worker.WorkerSettings &

# Khởi chạy FastAPI Server:
uvicorn app.main:app --reload --port 8000
```

#### 3. Migration & Quản lý Schema Database
Schema nằm trong `backend/migrations/` (`000_init.sql`, `001_...sql`, …). `python -m app.migrate` chạy các file **chưa chạy** theo thứ tự tên và ghi lại vào bảng `schema_migrations`; chạy lại nhiều lần không sao. Lệnh luôn dùng `DATABASE_URL_UNPOOLED` (URL **không qua pooler**).

| Tình huống | Lệnh |
| :--- | :--- |
| Database mới (trống) | `python -m app.migrate` |
| Database đã tạo từ `schema.sql` cũ (volume Docker cũ, Neon project VJAH) — chạy **một lần** | `python -m app.migrate --baseline 000_init` rồi `python -m app.migrate` |
| Thay đổi schema | thêm file mới `backend/migrations/00N_mo_ta.sql`, **không sửa** file đã chạy |

**Kiểm tra ràng buộc schema bằng kiểm thử tự động:**  
`pytest tests/test_schema_sql.py` (chạy trên database test riêng `lusia_test`, không ảnh hưởng tới database chính).

#### 4. Danh tính phát triển (Dev Identity - `AUTH_MODE=dev`)

Backend hiện chạy ở chế độ `AUTH_MODE=dev` (chế độ này tự động bị chặn nếu `APP_ENV=production`):
- Mặc định: Request học sinh dùng `DEV_STUDENT_USERNAME=minh8a`, giáo viên dùng `DEV_TEACHER_USERNAME=colan`.
- Chọn người dùng qua header HTTP: `X-Dev-User: <username>`.
- Tra cứu danh tính hiện tại:
  ```bash
  curl -s localhost:8000/me                            # minh8a (học sinh, tiếng Việt)
  curl -s -H "X-Dev-User: hana8a" localhost:8000/me    # hana8a (học sinh, tiếng Nhật)
  curl -s -H "X-Dev-User: colan"  localhost:8000/me    # colan (giáo viên)
  ```

#### 5. Chạy kiểm thử (Automated Tests)

```bash
pytest      # Tự động dùng database test lusia_test và AI provider giả lập (fake), không tốn token/chi phí
```

---

### 4. Khởi chạy Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Mở trình duyệt **Google Chrome** (cần thiết cho nhận diện giọng nói tiếng Việt độ trễ thấp qua Web Speech API):
- 🎓 **Giao diện Học sinh khiếm thị (Voice-first)**: <http://localhost:3000/learn>  
  *(Nhấn phím bất kỳ để bắt đầu, giữ phím Space để nói chuyện với LUSIA)*.
- 👩‍🏫 **Bảng điều khiển Giáo viên (Teacher Dashboard)**: <http://localhost:3000/dashboard>
- 📚 **Kiểm duyệt học liệu & Xuất bản SGK**: <http://localhost:3000/curation>
- 📊 **Giám sát Agent, Độ trễ & Token LLM**: <http://localhost:3000/monitor>
- 📖 **Tài liệu API Swagger**: <http://localhost:8000/docs>

> 💡 **Cấu hình kết nối API:** Mặc định frontend kết nối tới backend tại `http://localhost:8000`. Nếu đổi cổng backend, hãy tạo file `frontend/.env.local` với nội dung `NEXT_PUBLIC_API_URL=http://localhost:<cổng_mới>` và thêm origin tương ứng vào `FRONTEND_ORIGINS` trong `backend/.env`.

Khi API backend có thay đổi về endpoint hoặc kiểu dữ liệu:
```bash
npm run gen:api    # Tự động tạo lại TypeScript types tại src/lib/api-types.ts
```

---

## 🗺️ Lộ trình phát triển (Roadmap)

- [x] **Giai đoạn 1**: Định hình kiến trúc hệ sinh thái Multi-Agent, thiết kế tầng trợ năng Voice-first & triết lý **LUSIA**.
- [ ] **Giai đoạn 2 (VJAH 2026)**: Hoàn thiện bản mẫu MVP:
  - Agent gia sư đàm thoại giọng nói hai chiều (STT - TTS).
  - Tích hợp RAG tra cứu nội dung Sách giáo khoa.
  - Thử nghiệm tính năng Vision Agent mô tả đồ thị/hình ảnh cho người khiếm thị.
- [ ] **Giai đoạn 3**: Triển khai Teacher Dashboard và hệ thống đánh giá trắc nghiệm âm thanh.
- [ ] **Giai đoạn 4**: Hợp tác thử nghiệm thực tế tại các trường và trung tâm giáo dục chuyên biệt ở Việt Nam và Nhật Bản.

---

## 👥 Đội ngũ phát triển (Our Team)

Dự án được phát triển với tất cả tâm huyết vì một nền giáo dục hòa nhập:

- 🏆 **Cuộc thi**: Vietnam - Japan AI Hackathon 2026 (VJAH 2026)
- 💡 **Dự án**: **LUSIA** – *Listen • Understand • Share • Inspire • Assist*
- 🏫 **Đơn vị**: Trường Đại học Xây dựng Hà Nội (HUCE)

| Thành viên | Vai trò | GitHub |
| :--- | :--- | :--- |
| Triệu Quốc Đạt | _Đang cập nhật_ | [@DatTQ27](https://github.com/DatTQ27) |
| Phan Đức Duy | _Đang cập nhật_ | [@DuykoNgu](https://github.com/DuykoNgu) |

---

<div align="center">
  <sub>LUSIA • Công nghệ mở - Tri thức không giới hạn - Vì một nền giáo dục hòa nhập • VJAH 2026</sub>
</div>
