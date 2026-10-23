# Dev-grade image (hardened in the `deployment` change)
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
# Cache mount: build lại sau khi rớt mạng không phải tải lại từ đầu các wheel lớn (torch, pymupdf)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 10 -r requirements.txt
COPY app ./app
COPY migrations ./migrations
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
