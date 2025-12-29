#!/usr/bin/env bash

set -e

git pull

docker rm -f shell-coach 2>/dev/null || true

docker build -t shell-coach:latest .

docker run -d --name shell-coach --restart unless-stopped --env-file .env shell-coach:latest

