#!/bin/sh

for VAR in AWS_ACCESS_ID AWS_SECRET_KEY S3_BUCKET_NAME BBC_EMAIL BBC_PASSWORD
do
  VALUE=`eval "echo \\$$VAR"`

  if [ -z "${VALUE}" ]
  then
    echo Environment variable ${VAR} is not set >&2
    MISSING_VARIABLE=TRUE
  fi
done

if [ -n "${MISSING_VARIABLE}" ]
then
    echo Missing configuration, exiting. >&2
    exit 3
fi

# TODO add to cron and cat log if option set

cd /app
python -m bobcat -o /app/downloads -m 15