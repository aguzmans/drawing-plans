# CAD viewer service. Pinned base + pinned deps (see requirements.txt / CLAUDE.md).
FROM python:3.13.15-slim

WORKDIR /app

# deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY plans ./plans

EXPOSE 8000
# server binds 0.0.0.0, so a published port reaches the host.
CMD ["python", "server.py", "--port", "8000", "--plans", "/app/plans"]
