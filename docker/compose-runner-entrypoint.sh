#!/bin/sh
set -eu
mkdir -p "$GRADLE_USER_HOME" "$HOME"
cp -a /opt/gradle-cache/. "$GRADLE_USER_HOME/"
exec /opt/venv/bin/python /opt/verboflex/compose_capture.py "$@"
