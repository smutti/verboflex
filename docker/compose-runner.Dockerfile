# syntax=docker/dockerfile:1.8
# Supply a reviewed, digest-pinned image containing the current backend runtime,
# JDK 21, Android SDK and a credential-free, prewarmed Gradle dependency cache.
ARG CAPTURE_BASE_IMAGE
FROM ${CAPTURE_BASE_IMAGE}

USER root
COPY backend/src /opt/verboflex/src
COPY tools/compose_capture.py /opt/verboflex/compose_capture.py
COPY docker/compose-runner-entrypoint.sh /opt/verboflex/entrypoint.sh
RUN test -x /opt/venv/bin/python \
    && test -d /opt/android-sdk \
    && test -d /opt/gradle-cache \
    && test ! -e /opt/gradle-cache/gradle.properties \
    && chmod 755 /opt/verboflex/entrypoint.sh
ENV PYTHONPATH=/opt/verboflex/src \
    PYTHONDONTWRITEBYTECODE=1 \
    ANDROID_HOME=/opt/android-sdk \
    GRADLE_USER_HOME=/tmp/gradle \
    HOME=/tmp/capture-home
USER 65532:65532
ENTRYPOINT ["/opt/verboflex/entrypoint.sh"]
