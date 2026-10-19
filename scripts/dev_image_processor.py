from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "apps" / "image-processor"
BACKEND = APP / "backend"
LAMA = BACKEND / "lama_service"
FRONTEND_FILTER = "@apps/image-processor-frontend"
API_PORT = 8010
LAMA_PORT = 8011


def _venv_python(project: Path) -> Path:
    relative = Path("Scripts") / "python.exe" if os.name == "nt" else Path("bin") / "python"
    executable = project / ".venv" / relative
    if not executable.is_file():
        raise FileNotFoundError(
            f"Missing environment at {project / '.venv'}. Run the app launcher once to install it."
        )
    return executable


def _assert_port_free(port: int) -> None:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            raise RuntimeError(f"Port {port} is occupied; stop that service before using dev mode.")
    except OSError:
        return


def _lama_is_ready() -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{LAMA_PORT}/health", timeout=0.5) as response:
            return response.status == 200
    except OSError:
        return False


def _frontend_command() -> list[str]:
    if shutil.which("pnpm") is None:
        raise FileNotFoundError("pnpm is required to run the frontend dev server.")
    command = ["pnpm", "--filter", FRONTEND_FILTER, "dev"]
    return ["cmd.exe", "/d", "/s", "/c", " ".join(command)] if os.name == "nt" else command


def _stop_processes(processes: list[tuple[str, subprocess.Popen[bytes]]]) -> None:
    for _, process in processes:
        if process.poll() is None:
            process.terminate()
    for _, process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main() -> int:
    main_python = _venv_python(BACKEND)
    lama_python = _venv_python(LAMA)
    _assert_port_free(API_PORT)
    reuse_lama = _lama_is_ready()
    if not reuse_lama:
        _assert_port_free(LAMA_PORT)

    environment = os.environ.copy()
    environment["LAMA_SERVICE_PORT"] = str(LAMA_PORT)
    commands = [
        (
            "PaddleOCR API",
            [
                str(main_python),
                "-m",
                "uvicorn",
                "app.main:app",
                "--reload",
                "--host",
                "127.0.0.1",
                "--port",
                str(API_PORT),
            ],
            BACKEND,
        ),
    ]
    if not reuse_lama:
        commands.append(
            (
                "LaMa service",
                [
                    str(lama_python),
                    "-m",
                    "uvicorn",
                    "app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(LAMA_PORT),
                ],
                LAMA,
            )
        )
    commands.append(("Vite frontend", _frontend_command(), ROOT))
    processes: list[tuple[str, subprocess.Popen[bytes]]] = []
    try:
        for name, command, cwd in commands:
            print(f"[dev] Starting {name}...")
            process = subprocess.Popen(command, cwd=cwd, env=environment)
            processes.append((name, process))

        while True:
            for name, process in processes:
                status = process.poll()
                if status is not None:
                    print(f"[error] {name} exited with status {status}.")
                    return status or 1
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\n[dev] Stopping local services...")
        return 0
    finally:
        _stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
