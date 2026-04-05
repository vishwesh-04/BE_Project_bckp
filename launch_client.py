#!/usr/bin/env python3
"""
launch_client.py
================
Entry point for the Federated Learning Client desktop application.

Usage::

    python launch_client.py --client-id 1
    python launch_client.py --client-id 2 --auto-start
    CLIENT_ID=3 python launch_client.py

This is a thin wrapper around ui.client_ui.main.
"""
import sys
import os

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.client_ui.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
