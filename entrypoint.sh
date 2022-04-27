#!/bin/sh

info() {
  echo `date +"[%Y-%m-%dT%H:%M:%S%z]"` INFO $*
}

error() {
  echo `date +"[%Y-%m-%dT%H:%M:%S%z]"` ERROR $*
}

for VAR in AWS_ACCESS_ID AWS_SECRET_KEY S3_BUCKET_NAME BBC_EMAIL BBC_PASSWORD
do
  VALUE=`eval "echo \\$$VAR"`

  if [ -z "${VALUE}" ]
  then
    error Environment variable ${VAR} is not set.
    MISSING_VARIABLE=TRUE
  fi
done

if [ -n "${MISSING_VARIABLE}" ]
then
    info Missing configuration, exiting.
    exit 3
fi

# Show dependency versions
info `python --version`
info `chromium-browser --version`
info `ffmpeg -version | head -1`

# Run now
/app/run.sh

# Start cron in foreground for scheduled runs
exec crond -f -l 9
