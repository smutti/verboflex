# syntax=docker/dockerfile:1.8
# Use a private build context with credential-free gradle-cache/ and reviewed
# capture-gradle.properties (resource limits and offline placeholders only).
ARG TOOLCHAIN_IMAGE
ARG BACKEND_IMAGE
FROM ${BACKEND_IMAGE} AS backend
FROM ${TOOLCHAIN_IMAGE}
COPY --from=backend /opt/venv /opt/venv
COPY gradle-cache /opt/gradle-cache
COPY capture-gradle.properties /opt/capture-gradle.properties
RUN test ! -e /opt/gradle-cache/gradle.properties \
    && chmod -R a+rX /opt/gradle-cache /opt/venv \
    && chmod 644 /opt/capture-gradle.properties
