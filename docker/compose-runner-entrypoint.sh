#!/bin/sh
set -eu
mkdir -p "$GRADLE_USER_HOME" "$HOME"
# The immutable image shares dependency artifacts/metadata between containers.
# Gradle's mutable state and build outputs remain private to this render.
export GRADLE_RO_DEP_CACHE=/opt/gradle-cache/caches
/opt/venv/bin/python /opt/verboflex/compose_capture_cache.py \
    --seed /opt/gradle-cache --destination "$GRADLE_USER_HOME"
if [ -f /opt/capture-gradle.properties ]; then
    # Operator-reviewed resource limits and offline placeholders, never credentials.
    cp /opt/capture-gradle.properties "$GRADLE_USER_HOME/gradle.properties"
fi
exec /opt/venv/bin/python /opt/verboflex/compose_capture.py "$@"
