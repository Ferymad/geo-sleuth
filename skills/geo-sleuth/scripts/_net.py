"""HTTP helpers shared by service clients."""
from __future__ import annotations

import os
import subprocess

PROXY_HELP = "proxy URL or 'direct'"


def resolve_proxy(proxy: str | None = None) -> str | None:
    value = (os.environ.get("GEO_PROXY", "") if proxy is None else proxy).strip()
    return None if value.lower() in ("", "direct") else value


def curl_args(proxy: str | None = None) -> list[str]:
    value = resolve_proxy(proxy)
    # Clear NO_PROXY for an explicit proxy; ignore ambient proxies for direct mode.
    return ["--proxy", value, "--noproxy", ""] if value else ["--noproxy", "*"]


def fetch_bytes(url: str, proxy: str | None = None, timeout: int = 20,
                headers: dict[str, str] | None = None) -> bytes:
    cmd = ["curl", "-q", "-fsSL", "--max-time", str(timeout), *curl_args(proxy)]
    for name, value in (headers or {}).items():
        cmd += ["-H", f"{name}: {value}"]
    try:
        result = subprocess.run(cmd + [url], capture_output=True, timeout=timeout + 5)
    except FileNotFoundError:
        raise RuntimeError("Request failed: curl is not available; install curl and run doctor.py --network.") from None
    except subprocess.TimeoutExpired:
        # Never echo the command or raw exception: URLs and proxies may contain credentials.
        raise RuntimeError("Request failed: subprocess exceeded its time limit; run doctor.py --network to check connectivity.") from None
    except OSError:
        raise RuntimeError("Request failed: curl could not start; run doctor.py --network to check local tools.") from None
    if result.returncode:
        raise RuntimeError(f"Request failed (curl exit {result.returncode}); run doctor.py --network to check connectivity.")
    return result.stdout


def model_proxy_env(proxy: str | None = None) -> None:
    """Set the model downloader's process environment before importing its HTTP client."""
    value = resolve_proxy(proxy)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
                "http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        os.environ.pop(key, None)
    if value:
        os.environ.update(HTTP_PROXY=value, HTTPS_PROXY=value, ALL_PROXY=value)
    else:
        os.environ["NO_PROXY"] = "*"
