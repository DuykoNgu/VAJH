from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, teacher

app = FastAPI(title="LUSIA API")

# ponytail: chỉ mở cho frontend local, thêm domain thật khi deploy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(teacher.router)


@app.get("/health")
def health():
    return {"status": "ok"}
