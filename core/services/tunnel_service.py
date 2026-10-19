"""
Cloudflare Tunnel Service for YUNA Bot
Automatically manages the cloudflared tunnel process when TUNNEL_ENABLED is true.
Exposes the local Quart dashboard backend to a secure Cloudflare Zero Trust public hostname.
"""

from __future__ import annotations
import os
import sys
import shutil
import subprocess
from typing import Optional

_tunnel_process: Optional[subprocess.Popen] = None


def _find_cloudflared_binary() -> Optional[str]:
    # 1. Check in system PATH
    path_bin = shutil.which("cloudflared") or shutil.which("cloudflared.exe")
    if path_bin:
        return path_bin

    # 2. Check standard Linux installation paths
    for sys_path in ("/usr/local/bin/cloudflared", "/usr/bin/cloudflared", "/bin/cloudflared"):
        if os.path.isfile(sys_path):
            return sys_path

    # 3. Check root directory or common install locations
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    for candidate in ("cloudflared", "cloudflared.exe"):
        local_cand = os.path.join(root_dir, candidate)
        if os.path.isfile(local_cand):
            return local_cand

    return None


def _download_cloudflared_if_missing() -> Optional[str]:
    """Automatically downloads the appropriate cloudflared binary for Linux/Windows if missing."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if sys.platform == "win32":
        target = os.path.join(root_dir, "cloudflared.exe")
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    else:
        import platform
        machine = platform.machine().lower()
        if "aarch64" in machine or "arm64" in machine:
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
        else:
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        target = os.path.join(root_dir, "cloudflared")

    if os.path.isfile(target):
        return target

    try:
        import urllib.request
        print(f"[CLOUDFLARE TUNNEL] Auto-downloading cloudflared binary for {sys.platform} from {url}...", flush=True)
        urllib.request.urlretrieve(url, target)
        if sys.platform != "win32":
            os.chmod(target, 0o755)
        print(f"[CLOUDFLARE TUNNEL] Successfully downloaded cloudflared to {target}", flush=True)
        return target
    except Exception as err:
        print(f"[CLOUDFLARE TUNNEL] Could not auto-download cloudflared: {err}", flush=True)
        return None


def start_tunnel_if_enabled() -> None:
    """Launches Cloudflare Tunnel daemon in the background if TUNNEL_ENABLED is configured."""
    global _tunnel_process

    is_enabled = os.getenv("TUNNEL_ENABLED", "").lower() in ("true", "1", "yes")
    if not is_enabled:
        return

    env = os.getenv("ENVIRONMENT", "vps").strip().lower()
    if env == "local":
        allow_local = os.getenv("ALLOW_LOCAL_TUNNEL", "false").strip().lower() in ("true", "1", "yes")
        if not allow_local:
            print("[CLOUDFLARE TUNNEL] Skipping tunnel start in local environment (ENVIRONMENT=local) to prevent hijacking production VPS tunnel traffic.", flush=True)
            return

    token = os.getenv("CF_TUNNEL_TOKEN") or os.getenv("CLOUDFLARE_TUNNEL_TOKEN")
    if not token:
        print("[CLOUDFLARE TUNNEL] Warning: TUNNEL_ENABLED is true, but CF_TUNNEL_TOKEN is missing.", flush=True)
        return

    # Check if a cloudflared process is already running to prevent duplicate competing connectors
    if _tunnel_process and _tunnel_process.poll() is None:
        return

    cf_url = os.getenv("CF_TUNNEL_URL", "Cloudflare Edge")
    binary = _find_cloudflared_binary() or _download_cloudflared_if_missing()
    if not binary:
        print(
            f"[CLOUDFLARE TUNNEL] Tunnel enabled for {cf_url}. "
            "Note: 'cloudflared' executable not found in PATH or project root. "
            "If cloudflared is already installed as a Windows/systemd service or container sidecar, traffic will route normally.",
            flush=True
        )
        return

    try:
        if sys.platform != "win32" and os.path.isfile(binary):
            try:
                os.chmod(binary, 0o755)
            except Exception:
                pass

        cmd = [binary, "tunnel", "run", "--token", token]
        os.makedirs("logs", exist_ok=True)
        cf_log = open("logs/cloudflared.log", "a", encoding="utf-8")
        popen_kwargs = {"stdout": cf_log, "stderr": subprocess.STDOUT}
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        _tunnel_process = subprocess.Popen(
            cmd,
            **popen_kwargs
        )
        print(f"[CLOUDFLARE TUNNEL] Successfully started background Cloudflare Tunnel -> {cf_url} (PID: {_tunnel_process.pid}) | Logs: logs/cloudflared.log", flush=True)
    except Exception as e:
        print(f"[CLOUDFLARE TUNNEL] Failed to launch cloudflared process: {e}", flush=True)


def stop_tunnel() -> None:
    """Gracefully terminates cloudflared daemon on bot shutdown."""
    global _tunnel_process
    if _tunnel_process and _tunnel_process.poll() is None:
        try:
            _tunnel_process.terminate()
            _tunnel_process.wait(timeout=3)
        except Exception:
            try:
                _tunnel_process.kill()
            except Exception:
                pass
        _tunnel_process = None
