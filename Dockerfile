FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home appuser \
    && mkdir -p /app/instance \
    && chown -R appuser:appuser /app/instance
USER appuser

# Screening results (SQLite) live here; mount a volume to keep them across restarts:
#   docker run -v hiring-data:/app/instance ...
VOLUME ["/app/instance"]

EXPOSE 8000

# Set SECRET_KEY at runtime: docker run -e SECRET_KEY=... -v hiring-data:/app/instance -p 8000:8000 hiring-agent
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 300 app:app"]
