import argparse
import os
import platform
import subprocess
import sys
import time
import logging


LOGGER = logging.getLogger(__name__)


def _quote(value: str) -> str:
    return f'"{value}"'


def _bin_path(python_exec: str, executable: str) -> str:
    return os.path.join(os.path.dirname(python_exec), executable)


def _with_env(command: str, env_vars: dict[str, str], current_os: str, project_root: str) -> str:
    if current_os == "Windows":
        prefix = f"set PYTHONPATH={project_root}"
        for key, value in env_vars.items():
            prefix += f" && set {key}={value}"
        return f"{prefix} && {command}"

    exports = [f'export PYTHONPATH=$PYTHONPATH:"{project_root}"']
    exports.extend(f'export {key}="{value}"' for key, value in env_vars.items())
    return "; ".join(exports + [command])


def _supernode_command(project_root: str, python_exec: str, client_id: str, personalize: bool, superlink: str) -> str:
    node_config = f'client_id="{client_id}",client_personalize="{str(personalize).lower()}"'
    return (
        f'{_quote(_bin_path(python_exec, "flower-supernode"))} '
        f'--insecure --dir {_quote(project_root)} --superlink {_quote(superlink)} '
        f'--node-config {_quote(node_config)} client.client_app:app'
    )


def run_simulation():
    """Headless fallback: spawns all FL processes into system terminals (original behaviour)."""
    python_exec = sys.executable
    current_os = platform.system()
    project_root = os.path.abspath(os.getcwd())
    server_address = os.getenv("SERVER_ADDRESS", "0.0.0.0:45678")
    server_driver_address = os.getenv("SERVER_DRIVER_ADDRESS", "127.0.0.1:9091")
    client_server_address = os.getenv("CLIENT_SERVER_ADDRESS", "127.0.0.1:45678")

    commands = [
        (
            "SERVER",
            (
                f'{_quote(_bin_path(python_exec, "flower-superlink"))} --insecure '
                f'--fleet-api-address {_quote(server_address)} '
                f'--driver-api-address {_quote(server_driver_address)}; '
                f'{_quote(_bin_path(python_exec, "flower-server-app"))} --insecure '
                f'--dir {_quote(project_root)} --superlink {_quote(server_driver_address)} '
                'server.server_app:app'
            ),
            {},
        ),
        (
            "CLIENT-1",
            _supernode_command(project_root, python_exec, "1", False, client_server_address),
            {},
        ),
        (
            "CLIENT-2",
            _supernode_command(project_root, python_exec, "2", True, client_server_address),
            {},
        ),
        (
            "CLIENT-3",
            _supernode_command(project_root, python_exec, "3", True, client_server_address),
            {},
        ),
    ]

    for name, command, env_vars in commands:
        full_cmd = _with_env(command, env_vars, current_os, project_root)
        if current_os == "Windows":
            subprocess.Popen(f'start "{name}" cmd /k "{full_cmd}"', shell=True)
        elif current_os == "Linux":
            terminal = (
                "x-terminal-emulator"
                if subprocess.run(["which", "x-terminal-emulator"], capture_output=True).returncode == 0
                else "konsole"
            )
            subprocess.Popen([terminal, "-e", "bash", "-c", f"{full_cmd}; exec bash"])

        if name == "SERVER":
            time.sleep(2)

    LOGGER.info("All terminals launched. Monitor windows for logs.")


def _run_server_ui(extra_args: list[str]) -> int:
    """Launch the Server desktop application."""
    # Ensure project root is on path before importing
    root = os.path.abspath(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    from ui.server_ui.main import main as server_main
    return server_main(extra_args)


def _run_client_ui(extra_args: list[str]) -> int:
    """Launch the Client desktop application."""
    root = os.path.abspath(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    from ui.client_ui.main import main as client_main
    return client_main(extra_args)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    # ---------------------------------------------------------------
    # CLI: check for --ui / --server-ui / --client-ui flags BEFORE
    # passing the remaining args to argparse so existing scripts that
    # call main.py without flags keep working unchanged.
    # ---------------------------------------------------------------
    _argv = sys.argv[1:]

    if "--server-ui" in _argv:
        _argv.remove("--server-ui")
        sys.exit(_run_server_ui(_argv))

    if "--client-ui" in _argv:
        _argv.remove("--client-ui")
        sys.exit(_run_client_ui(_argv))

    if "--ui" in _argv:
        # --ui without --server-ui or --client-ui defaults to the server
        _argv.remove("--ui")
        LOGGER.info("--ui flag detected — launching Server UI (use --client-ui for client).")
        sys.exit(_run_server_ui(_argv))

    # Default: original headless simulation
    run_simulation()
