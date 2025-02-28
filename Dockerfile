FROM python:3.11-slim-bookworm

# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

# create the directories that will hold the mounted volumes
RUN mkdir -p /app/model
RUN mkdir -p /app/results


WORKDIR /app

# Copy source code (this stays inside the container)
COPY src/. ./src
COPY pyproject.toml .
COPY README.md .
# env
COPY .env .

CMD ["uv", "run", "ingest"]