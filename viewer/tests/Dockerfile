# Playwright E2E runner. Pinned base + pinned deps; the chromium build is pinned
# transitively by playwright==1.62.0.
FROM python:3.13.15-slim

WORKDIR /tests

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps chromium

COPY . .

# VIEWER_URL is injected by docker-compose; defaults to localhost for manual runs.
CMD ["pytest", "-q"]
