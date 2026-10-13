# syntax=docker/dockerfile:1.8
# Operator-only preparation image. Production renders run offline in a separate image.
FROM python:3.14-slim
ARG ANDROID_TOOLS_VERSION=15859902
ARG ANDROID_TOOLS_SHA256=4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jdk-headless git curl unzip fontconfig libxrender1 libxtst6 libxi6 \
    && rm -rf /var/lib/apt/lists/*
ENV ANDROID_HOME=/opt/android-sdk JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
RUN curl --fail --location --retry 3 \
      "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_TOOLS_VERSION}_latest.zip" \
      -o /tmp/android-tools.zip \
    && echo "${ANDROID_TOOLS_SHA256}  /tmp/android-tools.zip" | sha256sum --check \
    && mkdir -p /opt/android-sdk/cmdline-tools \
    && unzip -q /tmp/android-tools.zip -d /tmp/android-tools \
    && mv /tmp/android-tools/cmdline-tools /opt/android-sdk/cmdline-tools/latest \
    && rm -rf /tmp/android-tools* \
    && yes | /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager --licenses >/dev/null
RUN /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager \
    'platforms;android-36' 'build-tools;35.0.0' 'build-tools;36.0.0' \
    'platform-tools' 'ndk;27.0.12077973'
