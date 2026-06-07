FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
ENV PYTHONUNBUFFERED=1
EXPOSE 8080

# Production WSGI server. One worker (keeps the in-process season/bracket cache
# warm) + threads for concurrency. Generous timeout: the first hit on a universe
# runs a ~2s sim. (Even if a tool swaps this for `flask run`, app:create_app is
# now discoverable, so it still boots — see app/__init__.py.)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 120 wsgi:app"]
