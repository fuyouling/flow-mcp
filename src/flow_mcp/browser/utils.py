"""Browser process and port utilities."""
from __future__ import annotations

import os
import socket
from typing import Optional

# pyrefly: ignore [untyped-import]
import psutil
from loguru import logger


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def get_process_by_port(port: int) -> Optional[psutil.Process]:
    """Find process listening on a given port."""
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                if conn.pid:
                    try:
                        return psutil.Process(conn.pid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        return None
    except Exception as e:
        logger.debug(f"Error querying process by port: {e}")
    return None


def stop_browser(port: int = 9222) -> bool:
    """Stop the browser process listening on the given port."""
    proc = get_process_by_port(port)
    if not proc:
        logger.info(f"Port {port} is not occupied.")
        return True

    try:
        logger.info(f"Terminating process on port {port}: PID={proc.pid}, Name={proc.name()}")
        children = proc.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        proc.terminate()
        gone, alive = psutil.wait_procs(children + [proc], timeout=3)
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
        logger.info(f"Successfully stopped process on port {port}.")
        return True
    except Exception as e:
        logger.warning(f"Failed to stop browser on port {port}: {e}")
        return False


def kill_chrome_by_user_dir(user_data_dir: str) -> bool:
    """Terminate Chrome processes using a specific user data directory."""
    if not user_data_dir or not os.path.exists(user_data_dir):
        return False
    try:
        norm_dir = os.path.normcase(os.path.abspath(user_data_dir))
        killed_any = False
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            name = proc.info.get("name", "")
            if name and "chrome" in name.lower():
                cmdline = proc.info.get("cmdline") or []
                for arg in cmdline:
                    if "--user-data-dir=" in arg:
                        arg_dir = arg.split("=", 1)[1].strip("\"'")
                        if os.path.normcase(os.path.abspath(arg_dir)) == norm_dir:
                            logger.info(f"Found chrome process with matching user-data-dir (PID={proc.info['pid']}), terminating...")
                            try:
                                proc.kill()
                                killed_any = True
                            except psutil.NoSuchProcess:
                                pass
                            break
        return killed_any
    except Exception as e:
        logger.warning(f"Error scanning Chrome processes by user dir: {e}")
        return False
