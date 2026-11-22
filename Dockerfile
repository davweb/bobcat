# Use edge to get latest Chromium and ffmpeg
FROM alpine:latest AS base

# Use a builder image for compiling dependencies
FROM base AS builder

# Install python, uv, and the dependencies we need to build the python dependencies
RUN apk add --no-cache uv python3 gcc musl-dev libffi-dev python3-dev

# Copy dependency manifests
COPY pyproject.toml uv.lock /app/

# Install only production deps into .venv, using the locked versions
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=0 UV_PYTHON=python3
RUN uv sync --frozen --no-dev

# Build the main image
FROM base

# Link the published image to its GitHub repository
LABEL org.opencontainers.image.source=https://github.com/davweb/bobcat

# Install python and runtime dependencies
RUN apk add --no-cache python3 ffmpeg chromium chromium-chromedriver
# Copy the built python dependencies from the builder image
COPY --from=builder /app/.venv /app/.venv

WORKDIR /app

# Copy the app files
COPY bobcat bobcat
COPY logo.png entrypoint.sh run.sh .
RUN chmod +x run.sh

# Set up crontab
COPY crontab.txt .
RUN /usr/bin/crontab crontab.txt

# Make python unbuffered to keep logs as up to date as possible
ENV PYTHONUNBUFFERED=1

# Source the python virtual environment and run our entrypoint
CMD ["sh", "/app/entrypoint.sh"]
