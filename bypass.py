#!/usr/bin/env python3
"""
METATRON - bypass.py
Cloudflare WAF bypass using FlareSolverr + curl-impersonate.

Requirements:
  - FlareSolverr running: docker run -d --name=flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest
  - curl-impersonate installed: https://github.com/lwthiker/curl-impersonate
    Install: sudo apt install curl-impersonate  (or via binary)

Usage:
  from bypass import detect_cloudflare, get_cf_session, run_tool_bypass
"""

import os
import subprocess
import requests


FLARESOLVERR_URL = os.environ.get("FLARESOLVERR_URL", "http://localhost:8191/v1")

# curl-impersonate binary — tries chrome120 first, falls back to chrome
CURL_IMPERSONATE = os.environ.get("CURL_IMPERSONATE_BIN", "curl_chrome120")


# ─────────────────────────────────────────────
# DETECT CLOUDFLARE
# ─────────────────────────────────────────────

def detect_cloudflare(target: str) -> bool:
    """
    Quick check: does the target return CF headers or challenge page?
    Returns True if Cloudflare is detected.
    """
    url = target if target.startswith("http") else f"https://{target}"
    try:
        resp = requests.get(url, timeout=10, verify=False,
                            headers={"User-Agent": "Mozilla/5.0"})
        headers = {k.lower(): v for k, v in resp.headers.items()}
        body = resp.text[:2000]

        if "cf-ray" in headers:
            return True
        if "cf-mitigated" in headers:
            return True
        if "_cf_chl_opt" in body:
            return True
        if resp.status_code in (403, 503) and "cloudflare" in body.lower():
            return True
        return False
    except Exception:
        return False


# ─────────────────────────────────────────────
# FLARESOLVERR SESSION
# ─────────────────────────────────────────────

def get_cf_session(target: str) -> dict | None:
    """
    Use FlareSolverr to solve CF JS challenge.
    Returns dict with 'cookies' and 'userAgent', or None on failure.
    """
    url = target if target.startswith("http") else f"https://{target}"
    print(f"  [*] FlareSolverr solving CF challenge for {url}...")
    try:
        resp = requests.post(FLARESOLVERR_URL, json={
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 60000,
            "returnOnlyCookies": True
        }, timeout=90)
        data = resp.json()

        if data.get("status") != "ok":
            print(f"  [!] FlareSolverr error: {data.get('message')}")
            return None

        cookies = {c["name"]: c["value"] for c in data["solution"]["cookies"]}
        ua = data["solution"]["userAgent"]

        if "cf_clearance" not in cookies:
            print("  [!] cf_clearance not found — CF may require CAPTCHA")
            return None

        print(f"  [+] Got cf_clearance: {cookies['cf_clearance'][:40]}...")
        return {"cookies": cookies, "userAgent": ua, "url": url}

    except requests.exceptions.ConnectionError:
        print(f"  [!] FlareSolverr not running at {FLARESOLVERR_URL}")
        print(f"      Start with: docker run -d --name=flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest")
        return None
    except Exception as e:
        print(f"  [!] FlareSolverr error: {e}")
        return None


# ─────────────────────────────────────────────
# CURL-IMPERSONATE RUNNER
# ─────────────────────────────────────────────

def _build_cookie_header(cookies: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def run_curl_impersonate(url: str, session: dict, extra_args: list = None) -> str:
    """
    Run curl-impersonate with CF session cookies.
    Uses Chrome TLS fingerprint to bypass JA3 detection.
    """
    cookie_str = _build_cookie_header(session["cookies"])
    cmd = [
        CURL_IMPERSONATE,
        "-s",
        "--max-time", "30",
        "-H", f"User-Agent: {session['userAgent']}",
        "-H", f"Cookie: {cookie_str}",
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: en-US,en;q=0.5",
        "-H", "Accept-Encoding: gzip, deflate, br",
        "-H", "Connection: keep-alive",
        "-k",
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.stdout.strip() or result.stderr.strip()
    except FileNotFoundError:
        return (
            f"[!] curl-impersonate not found: {CURL_IMPERSONATE}\n"
            f"    Install: https://github.com/lwthiker/curl-impersonate/releases\n"
            f"    Or: sudo apt install curl-impersonate"
        )
    except subprocess.TimeoutExpired:
        return "[!] curl-impersonate timed out"


def run_headers_bypass(target: str, session: dict) -> str:
    """Fetch HTTP headers using curl-impersonate (bypasses CF JA3 check)"""
    url = target if target.startswith("http") else f"https://{target}"
    print(f"  [*] curl-impersonate headers {url}")
    return run_curl_impersonate(url, session, extra_args=["-I"])


def run_body_bypass(target: str, session: dict) -> str:
    """Fetch page body using curl-impersonate"""
    url = target if target.startswith("http") else f"https://{target}"
    print(f"  [*] curl-impersonate body {url}")
    return run_curl_impersonate(url, session)


# ─────────────────────────────────────────────
# NUCLEI WITH CF SESSION
# ─────────────────────────────────────────────

def run_nuclei_bypass(target: str, session: dict) -> str:
    """
    Run nuclei with CF clearance cookie injected via header flag.
    nuclei supports -H flag for custom headers.
    """
    url = target if target.startswith("http") else f"https://{target}"
    cookie_str = _build_cookie_header(session["cookies"])
    print(f"  [*] nuclei (CF bypass) -u {url}")

    cmd = [
        "nuclei",
        "-u", url,
        "-severity", "critical,high,medium",
        "-silent",
        "-no-color",
        "-timeout", "10",
        "-H", f"User-Agent: {session['userAgent']}",
        "-H", f"Cookie: {cookie_str}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return result.stdout.strip() or result.stderr.strip() or "[!] nuclei no output"
    except FileNotFoundError:
        return "[!] nuclei not found — run: nuclei -update-templates"
    except subprocess.TimeoutExpired:
        return "[!] nuclei timed out after 600s"


# ─────────────────────────────────────────────
# FFUF WITH CF SESSION
# ─────────────────────────────────────────────

def run_ffuf_bypass(target: str, session: dict) -> str:
    """Run ffuf with CF session cookie injected"""
    url = target if target.startswith("http") else f"https://{target}"
    fuzz_url = f"{url}/FUZZ"
    cookie_str = _build_cookie_header(session["cookies"])
    wordlist = "/usr/share/wordlists/dirb/common.txt"
    print(f"  [*] ffuf (CF bypass) -u {fuzz_url}")

    cmd = [
        "ffuf",
        "-u", fuzz_url,
        "-w", wordlist,
        "-mc", "200,201,301,302,403",
        "-t", "20",              # lower threads for CF
        "-timeout", "10",
        "-s",
        "-H", f"User-Agent: {session['userAgent']}",
        "-H", f"Cookie: {cookie_str}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.stdout.strip() or "[!] ffuf no output"
    except FileNotFoundError:
        return "[!] ffuf not found — run: sudo apt install ffuf"
    except subprocess.TimeoutExpired:
        return "[!] ffuf timed out"


# ─────────────────────────────────────────────
# FULL BYPASS RECON
# ─────────────────────────────────────────────

def run_bypass_recon(target: str) -> dict:
    """
    Full CF bypass recon pipeline:
    1. Detect CF
    2. FlareSolverr → get cf_clearance
    3. curl-impersonate headers
    4. nuclei with cookie
    5. ffuf with cookie
    """
    print(f"\n  [*] Cloudflare bypass mode for: {target}")

    # Step 1: get session
    session = get_cf_session(target)
    if not session:
        return {"bypass_error": "FlareSolverr failed — CF not bypassed"}

    results = {}
    results["cf_session"] = f"cf_clearance obtained. UA: {session['userAgent'][:60]}..."
    results["curl_headers_bypass"] = run_headers_bypass(target, session)
    results["nuclei_bypass"]       = run_nuclei_bypass(target, session)
    results["ffuf_bypass"]         = run_ffuf_bypass(target, session)

    return results
