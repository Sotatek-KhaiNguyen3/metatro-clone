# 🔱 METATRON
### Trợ lý Pentest tích hợp AI

<p align="center">
  <img src="screenshots/banner.png" alt="Metatron Banner" width="800"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python"/>
  <img src="https://img.shields.io/badge/OS-Parrot%20Linux-green?style=for-the-badge&logo=linux"/>
  <img src="https://img.shields.io/badge/AI-DeepSeek%20V3.2-red?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/API-OpenRouter-purple?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Local-Ollama-lightgrey?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/DB-MariaDB-orange?style=for-the-badge&logo=mariadb"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge"/>
</p>

---

## 📌 METATRON là gì?

**METATRON** là công cụ pentest tích hợp AI chạy trên CLI. Nhập một IP hoặc domain mục tiêu — METATRON tự động chạy pipeline recon thực (nmap, whatweb, curl, gobuster, nuclei, katana, ffuf...), đưa toàn bộ kết quả cho AI phân tích, phát hiện lỗ hổng có bằng chứng thực tế (không phải AI đoán), đề xuất exploit và khuyến nghị cách vá. Hỗ trợ 2 backend: **OpenRouter** (cloud, không cần GPU) và **Ollama** (local model). Mọi kết quả được lưu vào MariaDB với lịch sử scan đầy đủ.

---

## ✨ Tính năng

- 🤖 **Dual backend AI** — OpenRouter (cloud) hoặc Ollama (local), đổi bằng 1 biến môi trường
- 🔍 **Web app pentest pipeline** — nmap → whatweb → curl → gobuster → nuclei (mặc định)
- 🕷️ **Spider & Fuzz** — katana (crawl toàn bộ endpoint), ffuf (fuzz parameter tìm SQLi/LFI)
- ✅ **Evidence-based** — nuclei verify CVE thật bằng template, không phải AI đoán
- 🌐 **Tìm kiếm web** — DuckDuckGo + tra cứu CVE (không cần API key thêm)
- 🗄️ **MariaDB Backend** — lịch sử scan đầy đủ với 5 bảng liên kết
- ✏️ **Sửa / Xóa** — chỉnh sửa bất kỳ kết quả nào trực tiếp từ CLI
- 🔁 **Vòng lặp agentic** — AI có thể tự yêu cầu chạy thêm tool (gobuster, nuclei, katana...) giữa chừng
- 📤 **Xuất báo cáo** — PDF và HTML từ **[2] Xem lịch sử**

---

## 🖥️ Ảnh chụp màn hình

<p align="center">
  <img src="screenshots/main_menu.png" alt="Menu chính" width="700"/>
  <br><i>Menu chính</i>
</p>

<p align="center">
  <img src="screenshots/scan_running.png" alt="Đang chạy scan" width="700"/>
  <br><i>Công cụ recon đang chạy trên mục tiêu</i>
</p>

<p align="center">
  <img src="screenshots/ai_analysis.png" alt="AI phân tích" width="700"/>
  <br><i>Llama 3.3 70B phân tích kết quả scan</i>
</p>

<p align="center">
  <img src="screenshots/results.png" alt="Kết quả" width="700"/>
  <br><i>Lỗ hổng được lưu vào database</i>
</p>

<p align="center">
  <img src="screenshots/export_menu.png" alt="Menu xuất báo cáo" width="700"/>
  <br><i>Xuất báo cáo dạng PDF và/hoặc HTML</i>
</p>

---

## 🧱 Tech Stack

| Thành phần    | Công nghệ                                          |
|---------------|----------------------------------------------------|
| Ngôn ngữ      | Python 3                                           |
| Backend cloud | OpenRouter — DeepSeek V3.2 / Claude Haiku (mặc định) |
| Backend local | Ollama — huihui_ai/qwen3.5-abliterated:9b          |
| Database      | MariaDB                                            |
| OS            | Parrot OS / Kali Linux (Debian-based)              |
| Tìm kiếm      | DuckDuckGo (miễn phí, không cần key)              |
| Tools recon   | nmap, whatweb, curl, gobuster, nuclei, katana, ffuf |

---

## 🏗️ Kiến trúc lab

```
[Máy attacker]                            [EC2 - Target]
Parrot OS / Kali Linux                    Ubuntu 22.04
├── METATRON (metatron.py)      ──────►   └── Juice Shop :3000
├── OpenRouter API (AI trên cloud)
└── MariaDB (lưu kết quả)
```

> Juice Shop chạy trên EC2. METATRON và MariaDB chạy trên máy attacker. AI chạy trên cloud qua OpenRouter — không cần GPU, không cần tải model về máy.

---

## ⚙️ Cài đặt

### 1. Clone repository

```bash
git clone https://github.com/Sotatek-KhaiNguyen3/metatro-clone.git
cd METATRON
```

### 2. Tạo và kích hoạt virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Cài Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Cài system tools

```bash
# Core (bắt buộc)
sudo apt install -y nmap whatweb curl nikto

# gobuster và ffuf
sudo apt install -y gobuster ffuf

# nuclei và katana (Go binary — cần Go 1.21+)
sudo apt install -y golang-go
export PATH=$PATH:$(go env GOPATH)/bin
echo 'export PATH=$PATH:$(go env GOPATH)/bin' >> ~/.bashrc
source ~/.bashrc

go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
nuclei -update-templates
go install github.com/projectdiscovery/katana/cmd/katana@latest
```

### 5. Cài Cloudflare Bypass (tùy chọn — cần khi target dùng CF WAF)

**Bước 5.1 — FlareSolverr** (giải JS challenge, lấy `cf_clearance`):

```bash
docker run -d \
  --name=flaresolverr \
  -p 8191:8191 \
  -e LOG_LEVEL=info \
  --restart unless-stopped \
  ghcr.io/flaresolverr/flaresolverr:latest
```

Verify:
```bash
docker logs flaresolverr | grep "ready"
# FlareSolverr is ready!
```

**Bước 5.2 — curl-impersonate** (mimic Chrome TLS fingerprint, bypass JA3 detection):

```bash
# Debian/Ubuntu/Parrot/Kali
wget https://github.com/lwthiker/curl-impersonate/releases/latest/download/curl-impersonate-chrome.x86_64-linux-gnu.tar.gz
tar -xzf curl-impersonate-chrome.x86_64-linux-gnu.tar.gz
sudo mv curl_chrome* /usr/local/bin/
```

Verify:
```bash
curl_chrome120 --version
```

**Cách dùng trong METATRON:**

Khi scan target có Cloudflare, METATRON tự động detect và hỏi bypass. Hoặc chọn preset `[b]` trong tool menu:

```
  [b] Bypass  (CF bypass: FlareSolverr + curl-impersonate + nuclei + ffuf)
```

Pipeline bypass:
```
FlareSolverr → cf_clearance cookie
curl-impersonate → headers (Chrome TLS fingerprint)
nuclei -H "Cookie: cf_clearance=..." → CVE scan
ffuf -H "Cookie: cf_clearance=..." → dir brute-force
```

---

## 🤖 Cài đặt AI — Chọn backend

METATRON hỗ trợ 2 backend, chọn bằng biến môi trường `LLM_BACKEND`.

---

### Option A — OpenRouter (cloud, khuyến nghị)

Không cần GPU, không cần tải model. Chỉ cần API key.

**Bước 1 — Lấy API key**

1. Vào [openrouter.ai](https://openrouter.ai) → đăng ký (dùng Google được)
2. Vào **Keys** → **Create Key**
3. Copy key (`sk-or-v1-...`)

**Bước 2 — Set biến môi trường**

```bash
export LLM_BACKEND=openrouter
export OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxx
# OPENROUTER_MODEL mặc định là deepseek/deepseek-v3.2, không cần export trừ khi muốn đổi model
```

Thêm vào `~/.bashrc` để giữ qua các phiên:

```bash
echo 'export LLM_BACKEND=openrouter' >> ~/.bashrc
echo 'export OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxx' >> ~/.bashrc
source ~/.bashrc
```

**Các model đề xuất:**

| Model | Chất lượng | Chi phí |
|-------|------------|---------|
| `deepseek/deepseek-v3.2` | Tốt nhất, tự sửa hallucination | ~$0.01/scan |
| `anthropic/claude-haiku-4-5` | Nhiều vuln nhất (14/scan), nhanh | ~$0.063/scan |
| `meta-llama/llama-3.3-70b-instruct:free` | Miễn phí | Có rate limit |

---

### Option B — Ollama (local model)

Cần máy đủ RAM (≥16 GB cho model 9B). Không cần internet sau khi tải.

```bash
# Cài Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Tải model
ollama pull huihui_ai/qwen3.5-abliterated:9b

# Build Modelfile (đã có trong repo)
ollama create metatron-qwen -f Modelfile

# Set backend
export LLM_BACKEND=local
export OLLAMA_MODEL=huihui_ai/qwen3.5-abliterated:9b
export OLLAMA_URL=http://localhost:11434/api/generate
```

> **Lưu ý:** CPU-only inference rất chậm (~4-5 token/s). Cần GPU để dùng được trong thực tế.

---

### Kiểm tra

```bash
source venv/bin/activate
python llm.py
# Nhập target test khi được hỏi
```

---

## 🗄️ Cài đặt Database

### Bước 1 — Khởi động MariaDB

```bash
sudo systemctl start mariadb
sudo systemctl enable mariadb
```

### Bước 2 — Tạo database và user

```bash
mysql -u root
```

```sql
CREATE DATABASE metatron;
CREATE USER 'metatron'@'localhost' IDENTIFIED BY '123';
GRANT ALL PRIVILEGES ON metatron.* TO 'metatron'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### Bước 3 — Tạo các bảng

```bash
mysql -u metatron -p123 metatron
```

```sql
CREATE TABLE history (
    sl_no     INT AUTO_INCREMENT PRIMARY KEY,
    target    VARCHAR(255) NOT NULL,
    scan_date DATETIME NOT NULL,
    status    VARCHAR(50) DEFAULT 'active'
);

CREATE TABLE vulnerabilities (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    sl_no       INT,
    vuln_name   VARCHAR(255),
    severity    VARCHAR(50),
    port        VARCHAR(20),
    service     VARCHAR(100),
    description TEXT,
    FOREIGN KEY (sl_no) REFERENCES history(sl_no)
);

CREATE TABLE fixes (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    sl_no    INT,
    vuln_id  INT,
    fix_text TEXT,
    source   VARCHAR(50),
    FOREIGN KEY (sl_no) REFERENCES history(sl_no),
    FOREIGN KEY (vuln_id) REFERENCES vulnerabilities(id)
);

CREATE TABLE exploits_attempted (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    sl_no        INT,
    exploit_name VARCHAR(255),
    tool_used    VARCHAR(100),
    payload      TEXT,
    result       VARCHAR(100),
    notes        TEXT,
    FOREIGN KEY (sl_no) REFERENCES history(sl_no)
);

CREATE TABLE summary (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    sl_no        INT,
    raw_scan     LONGTEXT,
    ai_analysis  LONGTEXT,
    risk_level   VARCHAR(50),
    generated_at DATETIME,
    FOREIGN KEY (sl_no) REFERENCES history(sl_no)
);

EXIT;
```

Kiểm tra:

```bash
mysql -u metatron -p123 metatron -e "SHOW TABLES;"
# Phải thấy đủ 5 bảng: history, vulnerabilities, fixes, exploits_attempted, summary
```

---

## 🎯 Lab: Pentest Juice Shop trên EC2

Đây là lab khuyến nghị để test METATRON.

### Phần 1 — Dựng EC2 (Target)

**Bước 1.1 — Tạo EC2 instance**
- AMI: **Ubuntu 22.04 LTS**
- Instance type: **t2.medium** (2 vCPU, 4 GB RAM)
- Storage: 20 GB

**Bước 1.2 — Cấu hình Security Group (làm TRƯỚC khi launch)**

Chỉ cho phép IP của bạn — không mở public:

| Port | Protocol | Source |
|------|----------|--------|
| 22   | TCP      | `<your-ip>/32` |
| 3000 | TCP      | `<your-ip>/32` |

Kiểm tra IP của bạn:
```bash
curl ifconfig.me
```

**Bước 1.3 — SSH vào EC2**

```bash
ssh -i <your-key.pem> ubuntu@<EC2-public-ip>
```

**Bước 1.4 — Cài Docker**

```bash
sudo apt update && sudo apt install docker.io -y
sudo systemctl enable --now docker
```

**Bước 1.5 — Chạy Juice Shop**

```bash
sudo docker run -d -p 3000:3000 bkimminich/juice-shop
```

Kiểm tra từ máy attacker:
```bash
curl -o /dev/null -s -w "%{http_code}" http://<EC2-public-ip>:3000
# Kết quả mong đợi: 200
```

### Phần 2 — Chạy scan

```bash
# Đảm bảo đã set API key
export OPENROUTER_API_KEY=sk-or-v1-...

# Kích hoạt venv và chạy
source venv/bin/activate
python metatron.py
```

Chọn **[1] New Scan** → nhập IP public của EC2 → chọn tool recon → để METATRON phân tích.

---

## 🚀 Hướng dẫn sử dụng

### Khởi động METATRON

```bash
cd METATRON
source venv/bin/activate

# OpenRouter (cloud)
export LLM_BACKEND=openrouter
export OPENROUTER_API_KEY=sk-or-v1-...

# hoặc Ollama (local)
# export LLM_BACKEND=local

python metatron.py
```

### Các bước thao tác

**1. Menu chính:**
```
  [1]  New Scan
  [2]  View History
  [3]  Exit
```

**2. Chọn [1] New Scan → nhập target:**
```
[?] Enter target IP or domain: <EC2-public-ip>
```

**3. Chọn tool recon:**
```
  [ SELECT TOOLS TO RUN ]
  ── Core ──────────────────────────────
  [1] nmap
  [2] whatweb
  [3] curl headers
  [4] gobuster
  [5] nuclei
  ── Optional ──────────────────────────
  [6] nikto
  [7] katana (spider)
  [8] ffuf (fuzz)
  [9] whois
  [0] dig DNS
  ── Presets ───────────────────────────
  [a] Default  (nmap + whatweb + curl + gobuster + nuclei)
  [f] Full     (default + nikto + katana + ffuf)
```

**4.** METATRON chạy các tool, đưa kết quả cho AI, in ra phân tích.

**5.** Mọi thứ được lưu vào MariaDB tự động.

**6.** Từ **[2] View History**, chọn session để xem, sửa, xóa hoặc xuất báo cáo.

---

## 📁 Cấu trúc project

```
METATRON/
├── metatron.py       ← điểm vào chính (CLI)
├── db.py             ← kết nối MariaDB và toàn bộ CRUD
├── tools.py          ← chạy tool recon (nmap, whois, v.v.)
├── llm.py            ← giao tiếp OpenRouter API và vòng lặp agentic
├── search.py         ← tìm kiếm DuckDuckGo và tra cứu CVE
├── export.py         ← xuất báo cáo PDF và HTML
├── requirements.txt  ← Python dependencies
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🗃️ Schema Database

5 bảng liên kết với nhau qua `sl_no` (số thứ tự session) từ bảng `history`:

```
history
    │
    ├── vulnerabilities    ← lỗ hổng phát hiện, liên kết qua sl_no
    │       │
    │       └── fixes      ← cách vá cho từng lỗ hổng, liên kết qua vuln_id + sl_no
    │
    ├── exploits_attempted ← exploit đã thử, liên kết qua sl_no
    │
    └── summary            ← toàn bộ phân tích AI, liên kết qua sl_no
```

---

## 🧪 Kết quả test thực tế

### Test #1 — Juice Shop trên EC2

**Target:** `http://100.26.33.89:3000`  
**Model:** `metatron-qwen` (4B, CPU-only, Ollama local)  
**Ngày test:** 2026-04-07

---

**Bước 1 — Recon**

![New Scan](images/newscan.PNG)

METATRON chạy đủ 5 tool: nmap, whois, whatweb, curl, dig.

---

**Bước 2 — AI tự yêu cầu scan port 80/443**

![Scan port 80/443](images/newscan%20đến%2080-443%20check.PNG)

AI nhận thấy nmap không tìm thấy host (Juice Shop không trả lời TCP ping mặc định), tự request scan thêm port 80 và 443 — vòng lặp agentic hoạt động đúng.

---

**Bước 3 — Scan port 3000, phân tích lỗ hổng**

![Port 3000 và Vulnerability Analysis](images/port%203000%20-%20vuln%20ana.PNG)

AI tự request scan port 3000, phát hiện 3 lỗ hổng:

| # | Lỗ hổng | Mức độ |
|---|---------|--------|
| 1 | SQL Injection | HIGH |
| 2 | Cross-Site Scripting (XSS) | MEDIUM |
| 3 | Cross-Site Request Forgery (CSRF) | LOW |

> **Lưu ý:** Model hallucinate tech stack — báo `PHP 8.0, MySQL 5.7` trong khi Juice Shop thực tế chạy **Node.js + Angular + SQLite**.

---

**Bước 4 — Risk rating và Round 3**

![Rating và Round 3](images/rating%20-%20vào%20round%203.PNG)

AI đánh giá **Risk: HIGH**, tiếp tục search CVE-2021-44228 (Log4Shell) — không liên quan vì Juice Shop là Node.js, không phải Java. Đây là hallucination thứ hai.

---

**Bước 5 — Tổng kết và timeout**

![Tổng kết và Timeout](images/tổng%20kết%20và%20time%20out.PNG)

Round 4 bị timeout sau ~12 phút (CPU-only inference). Parser không extract được kết quả → DB lưu `0 vulns, Risk: UNKNOWN` dù AI đã phân tích ra 3 vuln ở Round 2.

**Tổng kết:**

| Hạng mục | Kết quả |
|----------|---------|
| Vòng lặp agentic | ✅ Hoạt động — AI tự request thêm tool |
| Recon pipeline | ✅ Hoạt động — đủ 5 tool |
| AI phân tích | ⚠️ Có output nhưng hallucinate tech stack và CVE |
| Parser → DB | ❌ Thất bại — lưu 0 vuln |
| Timeout | ❌ Round 4 timeout do 4B CPU-only quá chậm |

---

### Test #2 — Juice Shop trên EC2

**Target:** `http://100.26.33.89:3000`  
**Model:** `metatron-qwen` (4B, CPU-only, Ollama local)  
**Ngày test:** 2026-04-07

---

**Phân tích lỗ hổng**

![Scan lần 2 - Vuln 1](images/scan%20lần%202%20-%20vul%201.PNG)

| # | Lỗ hổng | Mức độ | Ghi chú |
|---|---------|--------|---------|
| 1 | CSRF vulnerability | HIGH | Gán nhầm CVE-2021-44228 (Log4Shell) |
| 2 | SQL Injection | MEDIUM | Gán CVE-2021-44229 — CVE không tồn tại |
| 3 | Missing X-Content-Type-Options | LOW | **Thật** — đọc từ curl headers thực tế |

---

**Phân tích exploit**

![Exploit Analysis](images/exploit%20ana.PNG)

AI đề xuất exploit cho CSRF và SQLi, bao gồm payload SQLmap và Burp Suite.

---

**So sánh Test #1 vs Test #2**

| Hạng mục | Test #1 | Test #2 |
|----------|---------|---------|
| Tech stack | PHP 8.0 + MySQL (sai hoàn toàn) | Node.js/PHP (bớt sai, nhận ra nginx) |
| Vuln thực tế | 3 vuln generic | 1 vuln thật (X-Content-Type-Options) |
| CVE | Log4Shell không liên quan | Gán sai + bịa CVE không tồn tại |
| IP target | Đúng | Hallucinate `192.168.1.1` khi gọi nmap |
| Parser → DB | Thất bại | Chưa verify |

**Cải thiện:** Nhận ra nginx từ curl headers, nhận diện Node.js, phát hiện 1 vuln thật.  
**Vấn đề mới:** Hallucinate IP khi gọi tool, bịa CVE không tồn tại.

---

### Kết luận

Kiến trúc pipeline đúng hướng. Các vấn đề cốt lõi khi dùng model 4B CPU-only:

1. **Parser thất bại** — AI có output nhưng parser không extract được → 0 vuln lưu vào DB
2. **Model nhỏ hallucinate nhiều** — bịa tech stack, CVE, IP
3. **Timeout** — inference CPU-only quá chậm cho vòng lặp 4+ round

**Setup hiện tại (Llama 3.3 70B qua OpenRouter) giải quyết cả ba:**
- Model lớn hơn tuân thủ format output tốt hơn → parser hoạt động
- Ít hallucinate hơn đáng kể
- Cloud inference: vài giây/round thay vì 12 phút

---

## ⚠️ Lưu ý quan trọng

- Chỉ dùng METATRON trên hệ thống bạn sở hữu hoặc có **văn bản cho phép** rõ ràng
- Scan trái phép là **vi phạm pháp luật**
- Stop hoặc terminate EC2 sau khi dùng xong để tránh phát sinh chi phí
- Juice Shop được thiết kế có lỗ hổng — không deploy trên môi trường production
- Tác giả không chịu trách nhiệm về bất kỳ hành vi lạm dụng công cụ này

---

## 👤 Tác giả

**Soorya Thejas**
- GitHub: [@sooryathejas](https://github.com/sooryathejas)

---

## 📄 Giấy phép

Dự án được cấp phép theo MIT License — xem file [LICENSE](LICENSE) để biết chi tiết.
