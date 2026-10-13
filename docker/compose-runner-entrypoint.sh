#!/bin/sh
set -eu
mkdir -p "$GRADLE_USER_HOME" "$HOME"
cp -a /opt/gradle-cache/. "$GRADLE_USER_HOME/"
if [ -f /opt/capture-gradle.properties ]; then
    # Operator-reviewed resource limits and offline placeholders, never credentials.
    cp /opt/capture-gradle.properties "$GRADLE_USER_HOME/gradle.properties"
fi
exec /opt/venv/bin/python /opt/verboflex/compose_capture.py "$@"
