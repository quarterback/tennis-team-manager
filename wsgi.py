"""Production WSGI entrypoint.

Served by gunicorn (see Dockerfile / Procfile):

    gunicorn wsgi:app

Use ONE worker with threads — the season/bracket results are cached in process
memory, so a single shared process keeps the cache warm; threads handle
concurrency.
"""
from app.web import create_app

app = create_app()
