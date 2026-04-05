#!/usr/bin/env python3
"""
launch_server.py
================
Entry point for the Federated Learning Server desktop application.

Usage::

    python launch_server.py
    python launch_server.py --auto-start

This is a thin wrapper around ui.server_ui.main.
"""
import sys
import os

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.server_ui.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
