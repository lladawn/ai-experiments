FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    TINY_MEMORY_DB=/data/memory.sqlite3

WORKDIR /app
COPY server.py http_server.py ./

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8000

CMD ["python", "http_server.py"]
