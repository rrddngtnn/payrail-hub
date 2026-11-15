FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Optional: Node.js enables the bundled Sentinel QuickJS fallback (sentinel_quickjs.py).
# Remove nodejs if you do not need QuickJS sentinel solving.
RUN apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api_python ./api_python
COPY scripts ./scripts
COPY sentinel_quickjs.py openai_sentinel_quickjs.js ./

RUN useradd -r -s /sbin/nologin payrail \
    && mkdir -p /app/data /app/run-output \
    && chown -R payrail:payrail /app

USER payrail
EXPOSE 8104

# Single worker is mandatory: in-memory job state and lock expect one process.
CMD ["uvicorn", "api_python.main:app", "--host", "0.0.0.0", "--port", "8104", "--workers", "1", "--proxy-headers"]
