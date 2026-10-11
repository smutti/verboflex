FROM postgres:18-alpine
RUN apk add --no-cache python3
COPY ops/database_backup.py /opt/verboflex/database_backup.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "/opt/verboflex/database_backup.py"]
CMD ["serve"]
