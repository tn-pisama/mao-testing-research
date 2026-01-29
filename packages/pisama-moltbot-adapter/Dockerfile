# PISAMA Moltbot Adapter Docker Image
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir websockets>=12.0 pydantic>=2.0.0 httpx>=0.25.0

# Copy and install pisama-core
COPY packages/pisama-core/src/pisama_core ./pisama_core

# Copy adapter code
COPY packages/pisama-moltbot-adapter/src/pisama_moltbot_adapter ./pisama_moltbot_adapter

# Run the adapter
CMD ["python", "-m", "pisama_moltbot_adapter.main"]
