FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --system --uid 10001 --no-create-home appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
USER 10001
EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8001/health/live',timeout=2)"
# Run migrations as a separate step (compose command / Kubernetes Job), not at container start.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
