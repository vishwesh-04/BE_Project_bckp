"""
server/__main__.py
------------------
Entry point for ``python -m server``.

Delegates to ``server.server_app.main_cli()`` which parses CLI args and
launches the Flower server infrastructure (SuperLink + SuperExec) in the foreground.
"""
from server.server_app import main_cli

if __name__ == "__main__":
    main_cli()
