"""Baseline web app (Flask) — the user-facing UI over the sim."""
from .server import create_app, main

__all__ = ["create_app", "main"]
