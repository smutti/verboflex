# syntax=docker/dockerfile:1.8
ARG BACKEND_IMAGE
FROM docker:28-cli AS cli
FROM ${BACKEND_IMAGE}
USER root
COPY --from=cli /usr/local/bin/docker /usr/local/bin/docker
COPY tools/compose_capture*.py /opt/verboflex/
ENV PYTHONPATH=/opt/verboflex
HEALTHCHECK NONE
ENTRYPOINT ["python", "/opt/verboflex/compose_capture_service.py"]
