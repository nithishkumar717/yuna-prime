"""Public, token-free GitHub access for the bot's read-only updater."""
from __future__ import annotations

import os
import subprocess


PUBLIC_REPOSITORY = "https://github.com/nithishkumar717/yuna-prime.git"


def get_github_credentials() -> tuple[str, str, str]:
    """Compatibility helper; public repository updates do not use credentials."""
    return "", "nithishkumar717", "nithishkumar717/yuna-prime"


def get_auth_remote_url() -> str:
    """Return the same public HTTPS URL; no token is ever embedded."""
    return PUBLIC_REPOSITORY


def get_clean_remote_url() -> str:
    return PUBLIC_REPOSITORY


def get_masked_remote_url() -> str:
    return PUBLIC_REPOSITORY


def get_git_env() -> dict[str, str]:
    """Disable interactive prompts and stored credential helpers for public fetches."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.pop("GITHUB_TOKEN", None)
    env["GIT_CONFIG_COUNT"] = "2"
    env["GIT_CONFIG_KEY_0"] = "credential.helper"
    env["GIT_CONFIG_VALUE_0"] = ""
    env["GIT_CONFIG_KEY_1"] = "http.https://github.com/.extraheader"
    env["GIT_CONFIG_VALUE_1"] = ""
    return env


def run_git_command(args: list[str], cwd: str, timeout: int = 60) -> tuple[int, str]:
    """Run Git without prompting, credential helpers, or global config mutation."""
    try:
        command = args if args and args[0] == "git" else ["git", *args]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=get_git_env(),
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return -1, f"Git command timed out after {timeout} seconds: {' '.join(args)}"
    except Exception as exc:
        return -1, f"Git execution error: {exc}"


def ensure_git_remote_configured(root_dir: str) -> tuple[bool, str]:
    """Set origin to the known public HTTPS URL without initializing/resetting a checkout."""
    git_dir_code, git_dir = run_git_command(["rev-parse", "--show-toplevel"], cwd=root_dir, timeout=10)
    if git_dir_code != 0:
        return False, f"Not a Git checkout; refusing to initialize or overwrite files: {git_dir}"
    remote_code, current = run_git_command(["remote", "get-url", "origin"], cwd=root_dir, timeout=10)
    if remote_code != 0:
        code, output = run_git_command(["remote", "add", "origin", PUBLIC_REPOSITORY], cwd=root_dir, timeout=10)
        if code != 0:
            return False, f"Could not configure public origin: {output}"
        return True, f"Configured origin as {PUBLIC_REPOSITORY}"
    if current.strip() != PUBLIC_REPOSITORY:
        code, output = run_git_command(["remote", "set-url", "origin", PUBLIC_REPOSITORY], cwd=root_dir, timeout=10)
        if code != 0:
            return False, f"Could not replace origin with the public HTTPS URL: {output}"
        return True, f"Updated origin to {PUBLIC_REPOSITORY}"
    return True, f"Using public origin {PUBLIC_REPOSITORY}"
