FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Test image:  docker build --target test -t nl-filter-test . && docker run --rm nl-filter-test
FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
CMD ["pytest", "-q"]


# Runtime image (the default target): only the app, no tests or dev tooling.
FROM base AS runtime
COPY *.py ./
COPY static ./static

# Run as a non-root user
RUN useradd --create-home appuser
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/api/examples')" || exit 1

CMD ["python", "server.py"]
