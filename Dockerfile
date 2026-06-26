FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
ENV PYTHONUNBUFFERED=1
EXPOSE 8080

# Production WSGI server. One worker (keeps the in-process season/bracket cache
# warm) + threads for concurrency. Generous timeout: most pages run a ~2s sim,
# but the first view of a recruit board runs the junior circuit over the whole
# recruit pool (tens of seconds) — the timeout must clear that or the worker is
# killed mid-build and the class never caches, so the page spins forever. (Even
# if a tool swaps this for `flask run`, app:create_app is now discoverable, so it
# still boots — see app/__init__.py.)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 300 wsgi:app"]
