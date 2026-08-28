FROM python:3.12-slim

WORKDIR /app

# git is required to install bizstruct-domain from its GitHub repo (git+https dependency)
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY src/ ./src/

RUN uv pip install --system --no-cache .

CMD ["python", "-m", "bizstruct_ml"]
