FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 northstar \
    && useradd --uid 1000 --gid northstar --home-dir /app --shell /usr/sbin/nologin northstar

COPY --chown=northstar:northstar backend /app/backend
COPY --chown=northstar:northstar scripts /app/scripts
COPY --chown=northstar:northstar data /app/data
COPY --chown=northstar:northstar frontend /app/frontend
COPY --chown=northstar:northstar admin-dashboard /app/admin-dashboard

# Runtime state and private enrollment data must come from the mounted state
# and data volumes, never from a cached image layer.
RUN rm -f /app/data/runtime-config.json /app/data/admin.sqlite3* /app/data/whatsapp_enrollments.xlsx \
    && rm -rf /app/data/feedback-media \
    && mkdir -p /app/data/feedback-media /app/state \
    && chown -R northstar:northstar /app/data /app/state

ENV PYTHONPATH=/app/backend

EXPOSE 8000

USER northstar

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8000/ready > /dev/null || exit 1

# Meta's verification token is carried in the webhook query string. Uvicorn's
# default access log prints complete query strings, so keep structured
# application logs while disabling that unsafe request-line log.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
