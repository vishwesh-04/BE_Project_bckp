"""
client/supernode_runner.py
--------------------------
Shared helper for launching a ``flower-supernode`` subprocess.

Used by:
  - ``client/__main__.py``  (standalone CLI mode)
  - ``ui/client/controller.py``  (FLSystemWorker in-UI mode)

This keeps all supernode startup logic in one place so fixes only happen here.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Callable

LOGGER = logging.getLogger(__name__)


def _resolve_supernode_bin() -> str:
    """Return the absolute path to ``flower-supernode`` inside the active venv,
    falling back to a bare PATH lookup if not found."""
    venv_bin = os.path.dirname(sys.executable)
    candidate = os.path.join(venv_bin, "flower-supernode")
    if os.path.isfile(candidate):
        return candidate
    return "flower-supernode"


def build_node_config(
    epochs: int | None = None,
    batch_size: int | None = None,
    lr: float | None = None,
    client_id: str | None = None,
    extra: dict | None = None,
) -> str:
    """Build the ``--node-config`` string accepted by ``flower-supernode``.

    Only non-None values are included so that the ClientApp can fall back to
    environment-variable / default resolution for unspecified fields.
    """
    parts: list[str] = []
    if client_id is not None:
        parts.append(f"client_id={client_id}")
    if epochs is not None:
        parts.append(f"local_epochs={epochs}")
    if batch_size is not None:
        parts.append(f"batch_size={batch_size}")
    if lr is not None:
        parts.append(f"learning_rate={lr}")
    if extra:
        for k, v in extra.items():
            parts.append(f"{k}={v}")
    return ",".join(parts)


def build_supernode_cmd(
    superlink: str,
    node_config: str,
    *,
    insecure: bool = True,
) -> list[str]:
    """Return the ``flower-supernode`` command list ready for ``subprocess.Popen``.

    Args:
        superlink:   Fleet API address, e.g. ``"127.0.0.1:45678"``.
        node_config: Comma-separated key=value string, e.g.
                     ``"client_id=1,local_epochs=3"``.
        insecure:    Pass ``--insecure`` flag (default True).
    """
    cmd = [_resolve_supernode_bin()]
    if insecure:
        cmd.append("--insecure")
    cmd += ["--superlink", superlink]
    if node_config:
        cmd += ["--node-config", node_config]
    return cmd


def run_supernode_blocking(
    superlink: str,
    node_config: str,
    *,
    insecure: bool = True,
    log_fn: Callable[[str], None] = print,
) -> int:
    """Launch ``flower-supernode`` and block until it exits.

    Streams stdout/stderr line-by-line to ``log_fn`` (defaults to ``print``
    for CLI usage; the UI passes ``self.log_signal.emit``).

    Returns the process exit code (0 = clean exit, non-zero = error).
    Raises ``FileNotFoundError`` if the binary cannot be found.
    """
    cmd = build_supernode_cmd(superlink, node_config, insecure=insecure)
    log_fn(f"[SUPERNODE] Launching: {' '.join(cmd)}")

    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                log_fn(f"[SUPERNODE] {line}")

        proc.wait()
        if proc.returncode == 0:
            log_fn("[SUPERNODE] Disconnected gracefully.")
        else:
            log_fn(f"[SUPERNODE] Exited with code {proc.returncode}.")
        return proc.returncode

    except FileNotFoundError:
        log_fn(
            "[ERROR] 'flower-supernode' binary not found. "
            "Ensure the Flower package is installed in the active venv "
            "and the venv bin directory is on PATH."
        )
        raise
    except Exception as exc:
        log_fn(f"[ERROR] Supernode error: {exc}")
        raise
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
