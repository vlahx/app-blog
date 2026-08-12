# Imagine generică FastAPI + Jinja (blog); refolosește aceeași imagine pentru mai multe instanțe
# (compose separat per site, volume-uri pentru db/content/static/.env).
FROM python:3.11-slim-bookworm

WORKDIR /app

# Runtime pentru Pillow (wheels) + locale minime
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        libopenjp2-7 \
        libwebp7 \
        libtiff6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV APP_PORT=8000

EXPOSE 8000

CMD ["python", "run.py"]
