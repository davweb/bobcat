FROM alpine:3.15.2 as base

# Use a builder image for compiling dependencies
FROM base as builder

# Install python and the dependencies we need to build the python dependencies
RUN apk add --no-cache python3 gcc musl-dev libffi-dev python3-dev 
# Build a virtual env to build the python dependencies in to
RUN python3 -m venv /app/venv
# Install python dependenices into temporary build image
COPY requirements.txt /app
RUN source /app/venv/bin/activate && pip3 install --requirement /app/requirements.txt

# Build the main image
FROM base

# Install python and runtime dependencies
RUN apk add --no-cache python3 ffmpeg chromium chromium-chromedriver
# Copy the build python dependencies from the builder image
COPY --from=builder /app/venv /app/venv

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
CMD source /app/venv/bin/activate && sh /app/entrypoint.sh
