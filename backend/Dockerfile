FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r mao && useradd -r -g mao mao

COPY requirements-prod.txt ./requirements.txt

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir sentence-transformers==2.3.1
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=mao:mao . .

USER mao

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
