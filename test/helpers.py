import io
import select
import socket
import subprocess
import threading
import time
from typing import Any, IO


def wait_for_output(stream: io.StringIO, text: str, timeout: float = 5.0) -> str:
    """Wait for a plain StringIO when replacing it with a synchronized stream is awkward."""
    deadline = time.monotonic() + timeout
    wakeup = threading.Event()
    while True:
        output = stream.getvalue()
        if text in output:
            return output
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"Expected {text!r} within {timeout}s. Output:\n{output}"
            )
        wakeup.wait(min(remaining, 0.01))


def wait_for_port(
    port: int,
    *,
    process: subprocess.Popen[str] | None = None,
    host: str = "127.0.0.1",
    timeout: float = 5.0,
) -> None:
    deadline = time.monotonic() + timeout
    while True:
        if process is not None and process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(
                f"Server exited before listening on {host}:{port}.\n"
                f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Port {host}:{port} was not ready within {timeout}s")
        try:
            with socket.create_connection((host, port), timeout=min(remaining, 0.1)):
                return
        except OSError:
            continue


def read_until(stream: IO[Any], text: str, timeout: float = 5.0) -> str:
    """Read subprocess output through the line containing text."""
    deadline = time.monotonic() + timeout
    lines: list[str] = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"Expected {text!r} within {timeout}s. Output:\n{''.join(lines)}"
            )
        readable, _, _ = select.select([stream], [], [], remaining)
        if not readable:
            continue
        line = stream.readline()
        if not line:
            raise RuntimeError(
                f"Output closed before {text!r} appeared. Output:\n{''.join(lines)}"
            )
        lines.append(line)
        if text in line:
            return "".join(lines)
