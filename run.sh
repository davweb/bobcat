#!/bin/sh

cd /app
export DATABASE_DIRECTORY=/bobcat
python -m bobcat -o /tmp
