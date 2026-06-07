"""Application layer: persistence, leagues, seasons, rating, recruiting, web."""


def create_app():
    """Flask application factory.

    Exposed on the top-level ``app`` package so that ``flask run`` / any WSGI
    server which auto-discovers a ``create_app`` factory in module ``app`` boots
    correctly — including Fly.io's generated ``flask run`` Dockerfile, which
    otherwise fails with "Failed to find Flask application or factory in module
    'app'". The import is done lazily *inside* the function so importing
    ``app.season`` / ``app.engine`` helpers never pulls in Flask.
    """
    from app.web import create_app as _create_app
    return _create_app()
