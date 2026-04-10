#!/usr/bin/env python3
"""
METATRON - llm.py
Dual-backend LLM interface:
  - local  : Ollama (metatron-qwen 9B, chạy trên máy hoặc EC2)
  - openrouter : Claude Haiku / Llama / Gemma qua OpenRouter API

Chọn backend bằng biến môi trường:
  export LLM_BACKEND=local        → dùng Ollama
  export LLM_BACKEND=openrouter   → dùng OpenRouter (mặc định)
"""

import re
import os
import requests
from openai import OpenAI
from tools import run_tool_by_command, run_nmap, run_curl_headers
from search import handle_search_dispatch

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

# backend: "local" hoặc "openrouter"
LLM_BACKEND = os.environ.get("LLM_BACKEND", "openrouter").lower()

# OpenRouter
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v3.2")
_openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
)

# Ollama local
OLLAMA_MODEL   = os.environ.get("OLLAMA_MODEL", "huihui_ai/qwen3.5-abliterated:9b")
OLLAMA_URL     = os.environ.get("OLLAMA_URL",   "http://localhost:11434/api/generate")

MAX_TOKENS     = 2048
MAX_TOOL_LOOPS = 5


# ─────────────────────────────────────────────
# SYSTEM PROMPT (dùng chung cho cả 2 backend)
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are METATRON, an elite AI penetration testing assistant.
You are precise, technical, and direct. No fluff.

You have access to real tools. To use them, write tags in your response:

  [TOOL: nmap -sV -sC -T4 --open 192.168.1.1]
  [TOOL: gobuster dir -u http://192.168.1.1 -w /usr/share/wordlists/dirb/common.txt -t 50 -q --no-error]
  [TOOL: nuclei -u http://192.168.1.1 -severity critical,high,medium -silent -no-color]
  [TOOL: katana -u http://192.168.1.1 -d 3 -silent -no-color]
  [TOOL: ffuf -u http://192.168.1.1/FUZZ -w /usr/share/wordlists/dirb/common.txt -mc 200,301,302,403 -t 50 -s]
  [TOOL: curl -sI http://192.168.1.1]
  [SEARCH: CVE-2021-44228 exploit]

TOOL USAGE GUIDE:
- nmap first → identify open ports and services
- gobuster → find hidden directories, admin panels, backup files
- nuclei → verify actual CVEs with templates (evidence-based, not guessing)
- katana → spider the app to discover all endpoints and forms
- ffuf → fuzz parameters for SQLi, LFI, IDOR
- Only use IPs/domains that appear in RECON DATA. Never invent IPs.
- Only reference CVE IDs you are confident exist.

STRICT RULES:
- Always analyze scan data thoroughly before suggesting exploits.
- Prioritize nuclei findings — they are verified, not guessed.
- List vulnerabilities with: name, severity, port, service.
- For each vulnerability, suggest a concrete fix.
- Format vulnerabilities clearly so they can be saved to a database.
- Always give a final risk rating: CRITICAL / HIGH / MEDIUM / LOW (no markdown bold).

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
# BACKEND: OLLAMA (local)
# ─────────────────────────────────────────────

def ask_ollama(prompt: str) -> str:
    """
    Gửi prompt đến Ollama đang chạy local (hoặc EC2).
    Model: metatron-qwen (9B) hoặc bất kỳ model nào đang chạy.
    """
    try:
        print(f"\n[*] Sending to Ollama ({OLLAMA_MODEL})...")
        payload = {
            "model":  OLLAMA_MODEL,
            "prompt": f"/no_think\n{SYSTEM_PROMPT}\n\n{prompt}",
            "stream": False,
            "options": {
                "num_predict": MAX_TOKENS,
                "temperature": 0.7,
            }
        }
        resp = requests.post(OLLAMA_URL, json=payload, timeout=3600)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()

    except requests.exceptions.ConnectionError:
        return "[!] Ollama không chạy. Khởi động bằng: ollama run metatron-qwen"
    except requests.exceptions.Timeout:
        return "[!] Ollama timeout — model quá chậm hoặc prompt quá dài."
    except Exception as e:
        return f"[!] Ollama error: {e}"


# ─────────────────────────────────────────────
# BACKEND: OPENROUTER (cloud)
# ─────────────────────────────────────────────

def ask_openrouter(prompt: str) -> str:
    """
    Gửi prompt đến OpenRouter cloud API.
    Model mặc định: anthropic/claude-haiku-4-5
    """
    if not os.environ.get("OPENROUTER_API_KEY"):
        return "[!] OPENROUTER_API_KEY not set. Run: export OPENROUTER_API_KEY=sk-or-v1-..."

    try:
        print(f"\n[*] Sending to {OPENROUTER_MODEL} (OpenRouter)...")
        resp = _openrouter_client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=MAX_TOKENS,
            temperature=0.7,
            extra_headers={
                "HTTP-Referer": "https://github.com/Sotatek-KhaiNguyen3/metatro-clone",
                "X-Title": "METATRON",
            },
        )
        return (resp.choices[0].message.content or "").strip()

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
# ROUTER — chọn backend tự động
# ─────────────────────────────────────────────

def ask_llm(prompt: str) -> str:
    """
    Gọi backend đang được chọn (local hoặc openrouter).
    Set bằng: export LLM_BACKEND=local | openrouter
    """
    if LLM_BACKEND == "local":
        return ask_ollama(prompt)
    else:
        return ask_openrouter(prompt)


# ─────────────────────────────────────────────
# TOOL DISPATCH
# ─────────────────────────────────────────────

def extract_tool_calls(response: str) -> list:
    """
    Extract tất cả [TOOL: ...] và [SEARCH: ...] từ AI response.
    Trả về list tuples: [("TOOL", "nmap -sV x.x.x.x"), ("SEARCH", "CVE...")]
    """
    calls = []
    for m in re.findall(r'\[TOOL:\s*(.+?)\]',   response):
        calls.append(("TOOL",   m.strip()))
    for m in re.findall(r'\[SEARCH:\s*(.+?)\]', response):
        calls.append(("SEARCH", m.strip()))
    return calls


def run_tool_calls(calls: list) -> str:
    """Chạy tất cả tool/search calls, trả về kết quả gộp."""
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
# PARSER
# ─────────────────────────────────────────────

def parse_vulnerabilities(response: str) -> list:
    """Parse VULN: lines thành list dict cho db.save_vulnerability()"""
    vulns = []
    lines = response.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("VULN:"):
            vuln = {"vuln_name": "", "severity": "medium",
                    "port": "", "service": "", "description": "", "fix": ""}
            for part in line.split("|"):
                part = part.strip()
                if part.startswith("VULN:"):
                    vuln["vuln_name"] = part.replace("VULN:", "").strip()
                elif part.startswith("SEVERITY:"):
                    vuln["severity"] = part.replace("SEVERITY:", "").strip().lower()
                elif part.startswith("PORT:"):
                    vuln["port"] = part.replace("PORT:", "").strip()
                elif part.startswith("SERVICE:"):
                    vuln["service"] = part.replace("SERVICE:", "").strip()

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
    """Parse EXPLOIT: lines thành list dict cho db.save_exploit()"""
    exploits = []
    lines = response.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("EXPLOIT:"):
            exploit = {"exploit_name": "", "tool_used": "",
                       "payload": "", "result": "unknown", "notes": ""}
            for part in line.split("|"):
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
    # match kể cả có ** hoặc ký tự thừa xung quanh (e.g. **MEDIUM**)
    match = re.search(r'RISK_LEVEL:\s*\*{0,2}(CRITICAL|HIGH|MEDIUM|LOW)\*{0,2}', response, re.IGNORECASE)
    return match.group(1).upper() if match else "UNKNOWN"


def parse_summary(response: str) -> str:
    match = re.search(r'SUMMARY:\s*(.+)', response, re.IGNORECASE)
    return match.group(1).strip() if match else response[:500]


# ─────────────────────────────────────────────
# MAIN ANALYSIS
# ─────────────────────────────────────────────

def analyse_target(target: str, raw_scan: str) -> dict:
    """
    Pipeline phân tích đầy đủ:
    1. Build prompt với recon data
    2. Gọi LLM (local hoặc cloud)
    3. Dispatch tool calls nếu AI yêu cầu
    4. Parse kết quả có cấu trúc
    5. Trả về dict sẵn sàng lưu DB
    """
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

    for loop in range(MAX_TOOL_LOOPS):
        response = ask_llm(full_conversation)

        print(f"\n{'─'*60}")
        print(f"[METATRON - Round {loop + 1}] (backend: {LLM_BACKEND})")
        print(f"{'─'*60}")
        print(response)

        vuln_count = len(parse_vulnerabilities(response))
        if vuln_count >= best_vuln_count:
            best_vuln_count = vuln_count
            best_response   = response

        if response.startswith("[!]"):
            print("\n[!] Backend error — stopping loop.")
            break

        tool_calls = extract_tool_calls(response)
        if not tool_calls:
            print("\n[*] No tool calls. Analysis complete.")
            break

        tool_results = run_tool_calls(tool_calls)

        full_conversation = (
            f"{full_conversation}\n\n"
            f"[YOUR PREVIOUS RESPONSE]\n{response}\n\n"
            f"[TOOL RESULTS]\n{tool_results}\n\n"
            f"Continue your analysis with this new information. "
            f"If analysis is complete, give the final RISK_LEVEL and SUMMARY."
        )

    final_response  = best_response or response
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
    print(f"[ llm.py test | backend: {LLM_BACKEND} ]\n")

    if LLM_BACKEND == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
        print("[!] Set your API key first:")
        print("    export OPENROUTER_API_KEY=sk-or-v1-...")
        exit(1)

    if LLM_BACKEND == "local":
        print(f"[+] Using Ollama model: {OLLAMA_MODEL}")
        print(f"[+] Ollama URL: {OLLAMA_URL}")
    else:
        print(f"[+] Using OpenRouter model: {OPENROUTER_MODEL}")

    target    = input("Test target: ").strip()
    test_scan = f"Test recon for {target} — nmap and whois data would appear here."
    result    = analyse_target(target, test_scan)

    print(f"\nRisk Level : {result['risk_level']}")
    print(f"Summary    : {result['summary']}")
    print(f"Vulns found: {len(result['vulnerabilities'])}")
    print(f"Exploits   : {len(result['exploits'])}")
