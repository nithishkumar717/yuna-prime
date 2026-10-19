"""
YUNA Git Authentication & Subprocess Management Engine
Centralized, safe handler for Git credentials, remote URLs, and subprocess execution.
Isolated from UI commands to prevent accidental breakage or credential leakage.
"""
from __future__ import annotations

import os
import sys
import base64
import subprocess
from typing import Tuple, Optional


def get_github_credentials() -> tuple[str, str, str]:
    """
    Extracts GitHub credentials safely from environment.
    Returns (token, username, repo_name).
    """
    token = os.getenv("GITHUB_TOKEN", "").strip()
    user = os.getenv("GITHUB_USERNAME", "nithishkumar717").strip()
    repo = os.getenv("GITHUB_REPO", "nithishkumar717/yuna-bot").strip()
    return token, user, repo


def get_auth_remote_url() -> str:
    """
    Builds the authenticated remote URL used for Git fetch/pull.
    Injects token for private repositories automatically.
    """
    token, user, repo = get_github_credentials()
    if token and repo:
        return f"https://{user}:{token}@github.com/{repo}.git"
    return f"https://github.com/{repo}.git"


def get_clean_remote_url() -> str:
    """
    Returns the clean, public-facing URL WITHOUT any tokens.
    Safe for Discord embeds, logs, and telemetry.
    """
    _, _, repo = get_github_credentials()
    return f"https://github.com/{repo}.git"


def get_masked_remote_url() -> str:
    """
    Returns a masked URL safe for debugging logs (e.g. ghp_eDf***hgZq).
    """
    token, user, repo = get_github_credentials()
    if not token:
        return f"https://github.com/{repo}.git"
    
    if len(token) > 8:
        masked = f"{token[:4]}...{token[-4:]}"
    else:
        masked = "****"
    return f"https://{user}:{masked}@github.com/{repo}.git"


def get_git_env() -> dict[str, str]:
    """
    Builds a secure Git environment with non-interactive prompt disabled.
    Prevents Git from ever hanging or asking for credentials on terminal.
    """
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"

    token, user, _ = get_github_credentials()
    if token and not token.startswith("github_pat_antigravity"):
        try:
            config_count = int(env.get("GIT_CONFIG_COUNT", "0"))
        except ValueError:
            config_count = 0
        basic_auth = base64.b64encode(f"{user}:{token}".encode("utf-8")).decode("ascii")
        env[f"GIT_CONFIG_KEY_{config_count}"] = "http.https://github.com/.extraheader"
        env[f"GIT_CONFIG_VALUE_{config_count}"] = f"AUTHORIZATION: basic {basic_auth}"
        env["GIT_CONFIG_COUNT"] = str(config_count + 1)

    return env


def run_git_command(args: list[str], cwd: str, timeout: int = 60) -> tuple[int, str]:
    """
    Safely executes a git CLI command.
    Returns (returncode, combined_stdout_stderr_output).
    Guarantees no terminal freeze and safe directory handling.
    """
    git_env = get_git_env()
    try:
        # Pre-flight: safe.directory to eliminate container dubious ownership warnings
        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", "*"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
            env=git_env
        )
    except Exception:
        pass

    try:
        res = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=git_env
        )
        output = (res.stdout or "") + (res.stderr or "")
        return res.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return -1, f"Git command timed out after {timeout} seconds: {' '.join(args)}"
    except Exception as e:
        return -1, f"Git execution error: {e}"


def ensure_git_remote_configured(root_dir: str) -> tuple[bool, str]:
    """
    Verifies that the git remote 'origin' is properly linked to the authenticated URL.
    Handles self-healing if .git does not exist.
    """
    git_dir = os.path.join(root_dir, ".git")
    auth_url = get_auth_remote_url()
    branch = os.getenv("GIT_BRANCH", "main")

    if not os.path.exists(git_dir):
        # Self-heal uninitialized repository
        run_git_command(["git", "init"], cwd=root_dir, timeout=10)
        run_git_command(["git", "remote", "add", "origin", auth_url], cwd=root_dir, timeout=10)
        code, out = run_git_command(["git", "fetch", "origin", branch], cwd=root_dir, timeout=60)
        if code != 0:
            return False, f"git fetch failed during initialization: {out}"
        run_git_command(["git", "checkout", "-B", branch, f"origin/{branch}"], cwd=root_dir, timeout=15)
        run_git_command(["git", "reset", "--hard", f"origin/{branch}"], cwd=root_dir, timeout=30)
        return True, "Initialized and synced fresh Git repository."

    # Update existing remote
    run_git_command(["git", "remote", "set-url", "origin", auth_url], cwd=root_dir, timeout=5)
    return True, "Remote origin verified and configured."
