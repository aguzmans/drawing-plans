FROM python:3.12-slim
# ezdxf + Pillow (the drawing addon imports PIL). No system libs needed.
RUN pip install --no-cache-dir ezdxf pillow
WORKDIR /app
COPY . /app
EXPOSE 8000
# server binds 0.0.0.0, so -p publishes it on the host.
CMD ["python", "server.py", "--port", "8000", "--plans", "/app/plans"]
