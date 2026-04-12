"""
client/__main__.py
------------------
Entry point for ``python -m client``.

Delegates to ``client.client_app.main()`` which parses CLI args and
launches the ``flower-supernode`` subprocess in the foreground.
"""
from client.client_app import main

if __name__ == "__main__":
    main()
