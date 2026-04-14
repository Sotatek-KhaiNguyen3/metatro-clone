#!/usr/bin/env python3
"""
METATRON - tools.py
Web app pentest tool runners — output returned as strings to feed into the LLM.

Default recon pipeline: nmap → whatweb → curl → gobuster → nuclei
Optional:              nikto, katana, ffuf, whois, dig
"""

import subprocess
try:
    from bypass import detect_cloudflare, run_bypass_recon, get_cf_session, \
                       run_nuclei_bypass, run_ffuf_bypass, run_headers_bypass
    BYPASS_AVAILABLE = True
except ImportError:
    BYPASS_AVAILABLE = False


# ─────────────────────────────────────────────
# BASE RUNNER
# ─────────────────────────────────────────────

def run_tool(command: list, timeout: int = 120) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout.strip()
        errors = result.stderr.strip()

        if output and errors:
            return output + "\n[STDERR]\n" + errors
        elif output:
            return output
        elif errors:
            return errors
        else:
            return "[!] Tool returned no output."

    except subprocess.TimeoutExpired:
        return f"[!] Timed out after {timeout}s: {' '.join(command)}"
    except FileNotFoundError:
        return f"[!] Tool not found: {command[0]} — install: sudo apt install {command[0]}"
    except Exception as e:
        return f"[!] Error running {command[0]}: {e}"


def _build_url(target: str) -> str:
    """Ensure target has http:// prefix for web tools."""
    if target.startswith("http://") or target.startswith("https://"):
        return target
    return f"http://{target}"


# ─────────────────────────────────────────────
# CORE TOOLS (default pipeline)
# ─────────────────────────────────────────────

def run_nmap(target: str) -> str:
    """nmap -sV -sC -T4 --open — port/service/version detection"""
    print(f"  [*] nmap -Pn -sV -sC -T4 --open {target}")
    return run_tool(["nmap", "-Pn", "-sV", "-sC", "-T4", "--open", target], timeout=180)


def run_whatweb(target: str) -> str:
    """whatweb -a 3 — tech stack, CMS, framework fingerprint"""
    url = _build_url(target)
    print(f"  [*] whatweb -a 3 {url}")
    return run_tool(["whatweb", "-a", "3", url], timeout=60)


def run_curl_headers(target: str) -> str:
    """curl -sI — HTTP headers, security headers, server info"""
    url = _build_url(target)
    print(f"  [*] curl -sI {url}")
    http_out = run_tool([
        "curl", "-sI", "--max-time", "10", "--location", url
    ], timeout=20)
    https_out = run_tool([
        "curl", "-sI", "--max-time", "10", "--location", "-k",
        url.replace("http://", "https://")
    ], timeout=20)
    return f"[HTTP Headers]\n{http_out}\n\n[HTTPS Headers]\n{https_out}"


def run_gobuster(target: str) -> str:
    """
    gobuster dir — brute-force directories and files.
    Wordlist: /usr/share/wordlists/dirb/common.txt (pre-installed Parrot/Kali)
    """
    url = _build_url(target)
    wordlist = "/usr/share/wordlists/dirb/common.txt"
    print(f"  [*] gobuster dir -u {url} -w {wordlist}")
    return run_tool([
        "gobuster", "dir",
        "-u", url,
        "-w", wordlist,
        "-t", "50",
        "--timeout", "10s",
        "-q",                   # quiet: no banner
        "--no-error",
    ], timeout=300)


def run_nuclei(target: str) -> str:
    """
    nuclei — CVE/misconfiguration scanner with community templates.
    Scans for critical and high severity only (fast mode).
    Run 'nuclei -update-templates' first if templates missing.
    """
    url = _build_url(target)
    print(f"  [*] nuclei -u {url} -severity critical,high,medium")
    return run_tool([
        "nuclei",
        "-u", url,
        "-severity", "critical,high,medium",
        "-silent",
        "-no-color",
        "-timeout", "10",
    ], timeout=600)


# ─────────────────────────────────────────────
# OPTIONAL TOOLS
# ─────────────────────────────────────────────

def run_nikto(target: str) -> str:
    """nikto -h — web server misconfig, outdated software (slow/noisy)"""
    url = _build_url(target)
    print(f"  [*] nikto -h {url}  (this may take a while...)")
    return run_tool(["nikto", "-h", url, "-nointeractive"], timeout=300)


def run_katana(target: str) -> str:
    """
    katana — fast web crawler/spider.
    Discovers endpoints, forms, JS links up to depth 3.
    Install: go install github.com/projectdiscovery/katana/cmd/katana@latest
    """
    url = _build_url(target)
    print(f"  [*] katana -u {url} -d 3")
    return run_tool([
        "katana",
        "-u", url,
        "-d", "3",
        "-silent",
        "-no-color",
        "-timeout", "10",
    ], timeout=300)


def run_ffuf(target: str) -> str:
    """
    ffuf — fast web fuzzer for parameter/path discovery.
    Fuzzes common paths with status filter 200,301,302,403.
    """
    url = _build_url(target)
    wordlist = "/usr/share/wordlists/dirb/common.txt"
    fuzz_url = f"{url}/FUZZ"
    print(f"  [*] ffuf -u {fuzz_url} -w {wordlist}")
    return run_tool([
        "ffuf",
        "-u", fuzz_url,
        "-w", wordlist,
        "-mc", "200,201,301,302,403",
        "-t", "50",
        "-timeout", "10",
        "-s",                   # silent mode (no banner)
    ], timeout=300)


def run_whois(target: str) -> str:
    """whois — domain registration info (useful for domain scope recon)"""
    # strip port if present
    host = target.split(":")[0]
    print(f"  [*] whois {host}")
    return run_tool(["whois", host], timeout=30)


def run_dig(target: str) -> str:
    """dig — DNS records A/MX/NS/TXT (useful for domain scope recon)"""
    host = target.split(":")[0]
    print(f"  [*] dig {host}")
    a   = run_tool(["dig", "+short", "A",   host], timeout=15)
    mx  = run_tool(["dig", "+short", "MX",  host], timeout=15)
    ns  = run_tool(["dig", "+short", "NS",  host], timeout=15)
    txt = run_tool(["dig", "+short", "TXT", host], timeout=15)
    return (
        f"[A Records]\n{a}\n\n"
        f"[MX Records]\n{mx}\n\n"
        f"[NS Records]\n{ns}\n\n"
        f"[TXT Records]\n{txt}"
    )


# ─────────────────────────────────────────────
# TOOL MENU
# ─────────────────────────────────────────────

TOOLS_MENU = {
    # core
    "1": ("nmap",            run_nmap),
    "2": ("whatweb",         run_whatweb),
    "3": ("curl headers",    run_curl_headers),
    "4": ("gobuster",        run_gobuster),
    "5": ("nuclei",          run_nuclei),
    # optional
    "6": ("nikto",           run_nikto),
    "7": ("katana (spider)", run_katana),
    "8": ("ffuf (fuzz)",     run_ffuf),
    "9": ("whois",           run_whois),
    "0": ("dig DNS",         run_dig),
}

TOOLS_DEFAULT = ["1", "2", "3", "4", "5"]   # run with choice "a"


# ─────────────────────────────────────────────
# PIPELINES
# ─────────────────────────────────────────────

def run_default_recon(target: str) -> dict:
    """
    Standard web app pentest pipeline:
    nmap → whatweb → curl → gobuster → nuclei

    If Cloudflare is detected, automatically switches to bypass mode:
    FlareSolverr → curl-impersonate → nuclei+cookie → ffuf+cookie
    """
    print(f"\n[*] Starting recon on: {target}")
    print("─" * 50)

    # Auto-detect Cloudflare and switch to bypass mode
    if BYPASS_AVAILABLE and detect_cloudflare(target):
        print("  [!] Cloudflare detected — switching to bypass mode")
        print("  [*] Requires FlareSolverr running on localhost:8191")
        cf_session = get_cf_session(target)
        if cf_session:
            results = {}
            results["nmap"]            = run_nmap(target)
            results["whatweb"]         = run_whatweb(target)
            results["curl_bypass"]     = run_headers_bypass(target, cf_session)
            results["nuclei_bypass"]   = run_nuclei_bypass(target, cf_session)
            results["ffuf_bypass"]     = run_ffuf_bypass(target, cf_session)
            print("─" * 50)
            print("[+] Recon complete (CF bypass mode).\n")
            return results
        else:
            print("  [!] FlareSolverr unavailable — falling back to standard recon")

    results = {}
    for key in TOOLS_DEFAULT:
        name, func = TOOLS_MENU[key]
        results[name] = func(target)

    print("─" * 50)
    print("[+] Recon complete.\n")
    return results


def format_recon_for_llm(results: dict) -> str:
    """Flatten recon results dict into one string for the LLM prompt."""
    output = ""
    for tool, data in results.items():
        output += f"\n{'='*50}\n"
        output += f"[ {tool.upper()} OUTPUT ]\n"
        output += f"{'='*50}\n"
        output += data.strip() + "\n"
    return output


def run_tool_by_command(command_str: str) -> str:
    """
    Called by LLM tool dispatch when AI writes [TOOL: gobuster dir -u http://x].
    Splits the string and runs it safely.
    """
    parts = command_str.strip().split()
    if not parts:
        return "[!] Empty command."

    blocked = ["rm", "dd", "mkfs", "shutdown", "reboot", "wget", "chmod"]
    if parts[0] in blocked:
        return f"[!] Blocked command: {parts[0]}"

    return run_tool(parts)


# ─────────────────────────────────────────────
# INTERACTIVE SELECTOR
# ─────────────────────────────────────────────

def interactive_tool_run(target: str) -> str:
    """Let user pick which tools to run. Returns combined output string."""
    print("\n[ SELECT TOOLS TO RUN ]")
    print("  ── Core ──────────────────────────────")
    for key in TOOLS_DEFAULT:
        name, _ = TOOLS_MENU[key]
        print(f"  [{key}] {name}")
    print("  ── Optional ──────────────────────────")
    for key in ["6", "7", "8", "9", "0"]:
        name, _ = TOOLS_MENU[key]
        print(f"  [{key}] {name}")
    print("  ── Presets ───────────────────────────")
    print("  [a] Default (nmap+whatweb+curl+gobuster+nuclei)")
    print("  [f] Full    (default + nikto + katana + ffuf)")
    print("  [b] Bypass  (CF bypass: FlareSolverr + curl-impersonate + nuclei + ffuf)")

    choice = input("\nChoice(s) e.g. 1 2 4 or a: ").strip().lower()

    if choice == "a":
        results = run_default_recon(target)
        return format_recon_for_llm(results)

    if choice == "f":
        results = run_default_recon(target)
        results["nikto"]  = run_nikto(target)
        results["katana"] = run_katana(target)
        if "ffuf_bypass" not in results:   # skip if bypass already ran ffuf
            results["ffuf"] = run_ffuf(target)
        return format_recon_for_llm(results)

    if choice == "b":
        if not BYPASS_AVAILABLE:
            print("[!] bypass.py not found")
            return ""
        cf_session = get_cf_session(target)
        if not cf_session:
            return "[!] FlareSolverr failed"
        results = {}
        results["nmap"]          = run_nmap(target)
        results["curl_bypass"]   = run_headers_bypass(target, cf_session)
        results["nuclei_bypass"] = run_nuclei_bypass(target, cf_session)
        results["ffuf_bypass"]   = run_ffuf_bypass(target, cf_session)
        return format_recon_for_llm(results)

    combined = {}
    for key in choice.split():
        if key in TOOLS_MENU:
            name, func = TOOLS_MENU[key]
            print(f"\n[*] Running {name}...")
            combined[name] = func(target)
        else:
            print(f"[!] Unknown option: {key}")

    return format_recon_for_llm(combined)


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    target = input("Enter test target (IP:port or domain): ").strip()
    results = run_default_recon(target)
    print(format_recon_for_llm(results))
