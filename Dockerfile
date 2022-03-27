FROM alpine:3.15.2
ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache python3
RUN ln -sf python3 /usr/bin/python
RUN python -m ensurepip
RUN pip3 install --no-cache --upgrade pip setuptools
# TODO use multipart build to avoid gcc etc in final image 
RUN apk add gcc musl-dev libffi-dev python3-dev 
COPY requirements.txt .
RUN pip3 install -r requirements.txt

RUN apk add ffmpeg
RUN apk add chromium chromium-chromedriver

WORKDIR /app
COPY bobcat ./bobcat
COPY logo.png entrypoint.sh .
CMD sh /app/entrypoint.sh