# Build from the backend/ folder:  docker build -f services/auth-service/Dockerfile backend
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --system --uid 10001 --no-create-home appuser
COPY services/auth-service/requirements.txt .
COPY shared /shared
RUN pip install --no-cache-dir -r requirements.txt /shared
COPY services/auth-service/app ./app
COPY services/auth-service/migrations ./migrations
COPY services/auth-service/alembic.ini .
USER 10001
EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8001/health/live',timeout=2)"
# Migrations run as a separate step (compose one-shot service / Kubernetes Job), not at container start.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
