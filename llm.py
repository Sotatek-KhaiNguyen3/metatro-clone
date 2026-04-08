#!/usr/bin/env python3
"""
METATRON - llm.py
OpenRouter API interface for METATRON.
Builds prompts, handles AI responses, runs tool dispatch loop.
Model: meta-llama/llama-3.3-70b-instruct:free (via OpenRouter)
"""

import re
import os
from openai import OpenAI
from tools import run_tool_by_command, run_nmap, run_curl_headers
from search import handle_search_dispatch

OPENROUTER_MODEL = "anthropic/claude-haiku-4-5"
MAX_TOKENS       = 4096
MAX_TOOL_LOOPS   = 5   # giảm từ 9 — cloud nhanh hơn, ít cần loop nhiều

_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
)


# ─────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are METATRON, an elite AI penetration testing assistant.
You are precise, technical, and direct. No fluff.

You have access to real tools. To use them, write tags in your response:

  [TOOL: nmap -sV 192.168.1.1]       → runs nmap or any CLI tool
  [SEARCH: CVE-2021-44228 exploit]   → searches the web via DuckDuckGo

STRICT RULES:
- Only use IP addresses and domain names that appear in the RECON DATA below. Never invent IPs.
- Only reference CVE IDs you are confident exist. If unsure, do not include a CVE ID.
- Always analyze scan data thoroughly before suggesting exploits.
- List vulnerabilities with: name, severity (critical/high/medium/low), port, service.
- For each vulnerability, suggest a concrete fix.
- If you need more information, use [SEARCH:] or [TOOL:].
- Format vulnerabilities clearly so they can be saved to a database.
- Always give a final risk rating: CRITICAL / HIGH / MEDIUM / LOW.

Output format for vulnerabilities (use this EXACTLY, one per line):
VULN: <name> | SEVERITY: <level> | PORT: <port> | SERVICE: <service>
DESC: <description>
FIX: <fix recommendation>

Output format for exploits:
EXPLOIT: <name> | TOOL: <tool> | PAYLOAD: <payload or description>
RESULT: <expected result>
NOTES: <any notes>

End your analysis with:
RISK_LEVEL: <CRITICAL|HIGH|MEDIUM|LOW>
SUMMARY: <2-3 sentence overall summary>
"""


# ─────────────────────────────────────────────
# OPENROUTER API CALL
# ─────────────────────────────────────────────

def ask_openrouter(prompt: str) -> str:
    """
    Send a prompt to OpenRouter and return the response string.
    System prompt is passed separately for better instruction following.
    """
    if not os.environ.get("OPENROUTER_API_KEY"):
        return "[!] OPENROUTER_API_KEY not set. Run: export OPENROUTER_API_KEY=sk-or-v1-..."

    try:
        print(f"\n[*] Sending to {OPENROUTER_MODEL}...")
        resp = _client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=MAX_TOKENS,
            temperature=0.7,
            extra_headers={
                "HTTP-Referer": "https://github.com/sooryathejas/METATRON",
                "X-Title": "METATRON",
            },
        )
        response = resp.choices[0].message.content or ""
        return response.strip()

    except Exception as e:
        err = str(e)
        if "api_key" in err.lower() or "401" in err:
            return "[!] Invalid API key. Check OPENROUTER_API_KEY."
        if "429" in err:
            return "[!] Rate limit hit. Wait a moment and retry."
        if "503" in err or "502" in err:
            return "[!] OpenRouter unavailable. Try again shortly."
        return f"[!] OpenRouter error: {e}"


# ─────────────────────────────────────────────
# TOOL DISPATCH
# ─────────────────────────────────────────────

def extract_tool_calls(response: str) -> list:
    """
    Extract all [TOOL: ...] and [SEARCH: ...] tags from AI response.
    Returns list of tuples: [("TOOL", "nmap -sV x.x.x.x"), ("SEARCH", "CVE...")]
    """
    calls = []

    tool_matches   = re.findall(r'\[TOOL:\s*(.+?)\]',   response)
    search_matches = re.findall(r'\[SEARCH:\s*(.+?)\]', response)

    for m in tool_matches:
        calls.append(("TOOL", m.strip()))
    for m in search_matches:
        calls.append(("SEARCH", m.strip()))

    return calls


def run_tool_calls(calls: list) -> str:
    """
    Execute all tool/search calls and return combined results string.
    """
    if not calls:
        return ""

    results = ""
    for call_type, call_content in calls:
        print(f"\n  [DISPATCH] {call_type}: {call_content}")

        if call_type == "TOOL":
            output = run_tool_by_command(call_content)
        elif call_type == "SEARCH":
            output = handle_search_dispatch(call_content)
        else:
            output = f"[!] Unknown call type: {call_type}"

        results += f"\n[{call_type} RESULT: {call_content}]\n"
        results += "─" * 40 + "\n"
        results += output.strip() + "\n"

    return results


# ─────────────────────────────────────────────
# PARSER — extract structured data from AI output
# ─────────────────────────────────────────────

def parse_vulnerabilities(response: str) -> list:
    """
    Parse VULN: lines from AI response into dicts.
    Returns list of vulnerability dicts ready for db.save_vulnerability()
    """
    vulns = []
    lines = response.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("VULN:"):
            vuln = {
                "vuln_name":   "",
                "severity":    "medium",
                "port":        "",
                "service":     "",
                "description": "",
                "fix":         ""
            }

            # parse header line: VULN: name | SEVERITY: x | PORT: x | SERVICE: x
            parts = line.split("|")
            for part in parts:
                part = part.strip()
                if part.startswith("VULN:"):
                    vuln["vuln_name"] = part.replace("VULN:", "").strip()
                elif part.startswith("SEVERITY:"):
                    vuln["severity"] = part.replace("SEVERITY:", "").strip().lower()
                elif part.startswith("PORT:"):
                    vuln["port"] = part.replace("PORT:", "").strip()
                elif part.startswith("SERVICE:"):
                    vuln["service"] = part.replace("SERVICE:", "").strip()

            # look ahead for DESC: and FIX: lines
            j = i + 1
            while j < len(lines) and j <= i + 5:
                next_line = lines[j].strip()
                if next_line.startswith("DESC:"):
                    vuln["description"] = next_line.replace("DESC:", "").strip()
                elif next_line.startswith("FIX:"):
                    vuln["fix"] = next_line.replace("FIX:", "").strip()
                j += 1

            if vuln["vuln_name"]:
                vulns.append(vuln)

        i += 1

    return vulns


def parse_exploits(response: str) -> list:
    """
    Parse EXPLOIT: lines from AI response into dicts.
    Returns list of exploit dicts ready for db.save_exploit()
    """
    exploits = []
    lines = response.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("EXPLOIT:"):
            exploit = {
                "exploit_name": "",
                "tool_used":    "",
                "payload":      "",
                "result":       "unknown",
                "notes":        ""
            }

            parts = line.split("|")
            for part in parts:
                part = part.strip()
                if part.startswith("EXPLOIT:"):
                    exploit["exploit_name"] = part.replace("EXPLOIT:", "").strip()
                elif part.startswith("TOOL:"):
                    exploit["tool_used"] = part.replace("TOOL:", "").strip()
                elif part.startswith("PAYLOAD:"):
                    exploit["payload"] = part.replace("PAYLOAD:", "").strip()

            j = i + 1
            while j < len(lines) and j <= i + 4:
                next_line = lines[j].strip()
                if next_line.startswith("RESULT:"):
                    exploit["result"] = next_line.replace("RESULT:", "").strip()
                elif next_line.startswith("NOTES:"):
                    exploit["notes"] = next_line.replace("NOTES:", "").strip()
                j += 1

            if exploit["exploit_name"]:
                exploits.append(exploit)

        i += 1

    return exploits


def parse_risk_level(response: str) -> str:
    """Extract RISK_LEVEL from AI response."""
    match = re.search(r'RISK_LEVEL:\s*(CRITICAL|HIGH|MEDIUM|LOW)', response, re.IGNORECASE)
    return match.group(1).upper() if match else "UNKNOWN"


def parse_summary(response: str) -> str:
    """Extract SUMMARY line from AI response."""
    match = re.search(r'SUMMARY:\s*(.+)', response, re.IGNORECASE)
    return match.group(1).strip() if match else response[:500]


# ─────────────────────────────────────────────
# MAIN ANALYSIS FUNCTION
# ─────────────────────────────────────────────

def analyse_target(target: str, raw_scan: str) -> dict:
    """
    Full analysis pipeline:
    1. Build initial prompt with scan data
    2. Send to OpenRouter model
    3. Run tool dispatch loop if AI requests tools
    4. Parse structured output
    5. Return everything ready for db.py to save

    Returns dict with:
      - full_response   : complete AI text
      - vulnerabilities : list of parsed vuln dicts
      - exploits        : list of parsed exploit dicts
      - risk_level      : CRITICAL/HIGH/MEDIUM/LOW
      - summary         : short summary text
      - raw_scan        : original scan dump
    """

    # ── Step 1: initial prompt ──────────────────
    initial_prompt = f"""TARGET: {target}

RECON DATA:
{raw_scan}

Analyze this target completely. Use [TOOL:] or [SEARCH:] if you need more information.
List all vulnerabilities found, fixes, and suggest exploits where applicable.
Remember: only use IPs/domains from the RECON DATA above.
"""

    full_conversation = initial_prompt
    best_response     = ""
    best_vuln_count   = 0

    # ── Step 2: tool dispatch loop ──────────────
    for loop in range(MAX_TOOL_LOOPS):
        response = ask_openrouter(full_conversation)

        print(f"\n{'─'*60}")
        print(f"[METATRON - Round {loop + 1}]")
        print(f"{'─'*60}")
        print(response)

        # track the response with most parsed vulns (không mất kết quả tốt)
        vuln_count = len(parse_vulnerabilities(response))
        if vuln_count >= best_vuln_count:
            best_vuln_count = vuln_count
            best_response   = response

        # stop if error from API
        if response.startswith("[!]"):
            print("\n[!] API error — stopping loop.")
            break

        # check for tool calls
        tool_calls = extract_tool_calls(response)
        if not tool_calls:
            print("\n[*] No tool calls. Analysis complete.")
            break

        # run all tool calls
        tool_results = run_tool_calls(tool_calls)

        # feed results back into conversation
        full_conversation = (
            f"{full_conversation}\n\n"
            f"[YOUR PREVIOUS RESPONSE]\n{response}\n\n"
            f"[TOOL RESULTS]\n{tool_results}\n\n"
            f"Continue your analysis with this new information. "
            f"If analysis is complete, give the final RISK_LEVEL and SUMMARY."
        )

    # dùng best_response thay vì chỉ lấy round cuối
    final_response  = best_response or response

    # ── Step 3: parse structured output ─────────
    vulnerabilities = parse_vulnerabilities(final_response)
    exploits        = parse_exploits(final_response)
    risk_level      = parse_risk_level(final_response)
    summary         = parse_summary(final_response)

    print(f"\n[+] Parsed: {len(vulnerabilities)} vulns, {len(exploits)} exploits | Risk: {risk_level}")

    return {
        "full_response":   final_response,
        "vulnerabilities": vulnerabilities,
        "exploits":        exploits,
        "risk_level":      risk_level,
        "summary":         summary,
        "raw_scan":        raw_scan
    }


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("[ llm.py test — OpenRouter direct query ]\n")

    if not os.environ.get("OPENROUTER_API_KEY"):
        print("[!] Set your API key first:")
        print("    export OPENROUTER_API_KEY=sk-or-v1-...")
        exit(1)

    print(f"[+] Using model: {OPENROUTER_MODEL}")
    target    = input("Test target: ").strip()
    test_scan = f"Test recon for {target} — nmap and whois data would appear here."
    result    = analyse_target(target, test_scan)

    print(f"\nRisk Level : {result['risk_level']}")
    print(f"Summary    : {result['summary']}")
    print(f"Vulns found: {len(result['vulnerabilities'])}")
    print(f"Exploits   : {len(result['exploits'])}")
