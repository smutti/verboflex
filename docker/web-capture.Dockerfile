# syntax=docker/dockerfile:1.8
# Synthetic reference image. A private application uses its reviewed lock and profile.
FROM node:20.20.0-bookworm-slim AS angular
WORKDIR /opt/application-dependencies
COPY tools/fixtures/angular-web/package.json tools/fixtures/angular-web/package-lock.json ./
RUN npm ci --ignore-scripts && npm rebuild esbuild

FROM mcr.microsoft.com/playwright:v1.62.1-noble
USER root
COPY --from=angular /usr/local/bin/node /opt/node20/bin/node
COPY --from=angular /opt/application-dependencies /opt/application-dependencies
WORKDIR /opt/web-runtime
COPY tools/web-runtime/package.json tools/web-runtime/package-lock.json ./
RUN npm ci --ignore-scripts
COPY tools/web-runtime/*.mjs ./
COPY tools/fixtures/angular-web/runner-profile.json /opt/web-profile.json
ENV HOME=/tmp PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
USER 65532:65532
ENTRYPOINT ["node", "/opt/web-runtime/run.mjs"]
