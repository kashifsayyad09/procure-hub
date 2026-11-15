# Build from the backend/ folder:  docker build -f services/quotation-service/Dockerfile backend
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --system --uid 10001 --no-create-home appuser
COPY services/quotation-service/requirements.txt .
COPY shared /shared
RUN pip install --no-cache-dir -r requirements.txt /shared
COPY services/quotation-service/app ./app
COPY services/quotation-service/migrations ./migrations
COPY services/quotation-service/alembic.ini .
USER 10001
EXPOSE 8005
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8005/health/live',timeout=2)"
# Migrations run as a separate step (compose one-shot service / Kubernetes Job), not at container start.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8005"]
