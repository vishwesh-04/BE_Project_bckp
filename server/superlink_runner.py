"""
server/superlink_runner.py
--------------------------
Shared helper for launching the Flower server-side infrastructure:
  1. ``flower-superlink``  — central orchestrator / broker
  2. ``flower-superexec``  — ServerApp executor (replaces deprecated flwr-serverapp)

Used by:
  - ``server/__main__.py``   (standalone CLI mode: ``python -m server``)
  - ``server-starter.sh``    (shell wrapper — calls ``python -m server``)

This consolidates all server startup logic in one place so fixes only happen here.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from typing import Callable

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Binary resolution
# ---------------------------------------------------------------------------

def _resolve_bin(name: str) -> str:
    """Return absolute path to *name* inside the active venv, falling back to PATH."""
    venv_bin = os.path.dirname(sys.executable)
    candidate = os.path.join(venv_bin, name)
    if os.path.isfile(candidate):
        return candidate
    return name


def resolve_superlink_bin() -> str:
    return _resolve_bin("flower-superlink")


def resolve_superexec_bin() -> str:
    # flower-superexec is the modern replacement for the deprecated flwr-serverapp
    return _resolve_bin("flower-superexec")


# ---------------------------------------------------------------------------
# Command builders
# ---------------------------------------------------------------------------

def build_superlink_cmd(
    fleet_api_address: str,
    serverappio_api_address: str,
    *,
    insecure: bool = True,
) -> list[str]:
    """Return the ``flower-superlink`` command list.

    Args:
        fleet_api_address:       Address clients connect to, e.g. ``"0.0.0.0:45678"``.
        serverappio_api_address: Internal ServerApp I/O address, e.g. ``"127.0.0.1:9091"``.
        insecure:                Pass ``--insecure`` (default True).
    """
    cmd = [resolve_superlink_bin()]
    if insecure:
        cmd.append("--insecure")
    cmd += [
        "--fleet-api-address", fleet_api_address,
        "--serverappio-api-address", serverappio_api_address,
    ]
    return cmd


def build_superexec_cmd(
    serverappio_api_address: str,
    *,
    insecure: bool = True,
) -> list[str]:
    """Return the ``flower-superexec`` command list.

    Args:
        serverappio_api_address: Must match the address given to SuperLink.
        insecure:                Pass ``--insecure`` (default True).

    Note:
        ``--plugin-type serverapp`` is required by flower-superexec to tell it
        which role to play. Without it the process exits immediately with code 2.
    """
    cmd = [resolve_superexec_bin()]
    if insecure:
        cmd.append("--insecure")
    cmd += [
        "--appio-api-address", serverappio_api_address,
        "--plugin-type", "serverapp",
    ]
    return cmd


# ---------------------------------------------------------------------------
# Port helpers
# ---------------------------------------------------------------------------

def _free_tcp_port(port: int) -> None:
    """Kill any process currently listening on *port* (best-effort)."""
    try:
        result = subprocess.run(
            ["fuser", f"{port}/tcp"],
            capture_output=True,
            text=True,
        )
        pids = result.stdout.strip().split()
        for pid_str in pids:
            try:
                os.kill(int(pid_str), signal.SIGKILL)
                LOGGER.info("Freed port %d (killed pid %s)", port, pid_str)
            except (ProcessLookupError, ValueError):
                pass
    except FileNotFoundError:
        # fuser not available on all systems; skip silently
        pass


def _port_from_address(address: str) -> int | None:
    """Extract the integer port from ``host:port`` string."""
    try:
        return int(address.rsplit(":", 1)[-1])
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Main blocking launcher
# ---------------------------------------------------------------------------

def run_server_blocking(
    fleet_api_address: str,
    serverappio_api_address: str,
    *,
    insecure: bool = True,
    superlink_startup_delay: float = 2.0,
    free_port_before_start: bool = True,
    log_fn: Callable[[str], None] = print,
) -> int:
    """Start SuperLink + SuperExec and block until both exit.

    SuperLink is started first (background), then SuperExec is started after
    *superlink_startup_delay* seconds and becomes the foreground process.
    On exit (or Ctrl+C), SuperLink is terminated.

    Args:
        fleet_api_address:       Fleet API address for clients to connect to.
        serverappio_api_address: Internal ServerApp I/O address.
        insecure:                Use insecure mode (default True).
        superlink_startup_delay: Seconds to wait after starting SuperLink before
                                 launching SuperExec (gives SuperLink time to bind).
        free_port_before_start:  Kill any process on the appio port before starting.
        log_fn:                  Callable to emit log lines (``print`` for CLI,
                                 Qt signal emit for UI).

    Returns:
        Exit code of the SuperExec process.
    """
    if free_port_before_start:
        appio_port = _port_from_address(serverappio_api_address)
        if appio_port:
            _free_tcp_port(appio_port)

    superlink_cmd = build_superlink_cmd(
        fleet_api_address, serverappio_api_address, insecure=insecure
    )
    superexec_cmd = build_superexec_cmd(serverappio_api_address, insecure=insecure)

    log_fn(f"[SUPERLINK] Launching: {' '.join(superlink_cmd)}")

    superlink_proc: subprocess.Popen | None = None
    superexec_proc: subprocess.Popen | None = None

    def _terminate_all() -> None:
        for proc, name in [(superexec_proc, "SuperExec"), (superlink_proc, "SuperLink")]:
            if proc is not None and proc.poll() is None:
                log_fn(f"[SERVER] Stopping {name}...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

    try:
        # ── 1. Start SuperLink in background ──────────────────────────────
        superlink_proc = subprocess.Popen(
            superlink_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        log_fn(f"[SUPERLINK] Started (pid={superlink_proc.pid}). "
               f"Waiting {superlink_startup_delay}s before launching SuperExec...")

        # Brief stream of superlink early output (non-blocking peek)
        time.sleep(superlink_startup_delay)

        # ── 2. Start SuperExec (foreground) ──────────────────────────────
        log_fn(f"[SUPEREXEC] Launching: {' '.join(superexec_cmd)}")
        superexec_proc = subprocess.Popen(
            superexec_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # ── 3. Stream both processes' output ─────────────────────────────
        # We stream SuperExec in the main loop. SuperLink output is drained
        # in a background thread to prevent the pipe buffer from blocking.
        import threading

        def _drain(proc: subprocess.Popen, prefix: str) -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    log_fn(f"[{prefix}] {line}")

        superlink_thread = threading.Thread(
            target=_drain, args=(superlink_proc, "SUPERLINK"), daemon=True
        )
        superlink_thread.start()

        assert superexec_proc.stdout is not None
        for line in superexec_proc.stdout:
            line = line.rstrip()
            if line:
                log_fn(f"[SUPEREXEC] {line}")

        superexec_proc.wait()
        exit_code = superexec_proc.returncode

        if exit_code == 0:
            log_fn("[SERVER] SuperExec exited gracefully.")
        else:
            log_fn(f"[SERVER] SuperExec exited with code {exit_code}.")

        return exit_code

    except FileNotFoundError as exc:
        log_fn(
            f"[ERROR] Binary not found: {exc}. "
            "Ensure the Flower package is installed in the active venv."
        )
        raise
    except KeyboardInterrupt:
        log_fn("\n[SERVER] Interrupted — shutting down.")
        return 0
    finally:
        _terminate_all()
