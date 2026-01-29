# PISAMA Moltbot Adapter Docker Image
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy adapter code
COPY src/ ./src/

# Install adapter package
RUN pip install --no-cache-dir -e .

# Run the adapter
CMD ["python", "-m", "pisama_moltbot_adapter.main"]
