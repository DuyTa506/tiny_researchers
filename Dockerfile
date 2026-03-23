FROM python:3.11-slim

# Keeps Python from generating .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Ensures stdout/stderr are flushed immediately
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency manifests first (layer cache)
COPY pyproject.toml ./
COPY README.md ./

# Install all optional dependency groups in one pass
RUN uv pip install --system -e ".[channels]"

# Copy source
COPY claw/ ./claw/

# Create workspace directory
RUN mkdir -p /workspace

# Default workspace
ENV CLAW_WORKSPACE=/workspace

EXPOSE 8080

CMD ["claw", "serve", "--workspace", "/workspace", "--webhook-host", "0.0.0.0", "--webhook-port", "8080"]
