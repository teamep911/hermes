# Architecture — Phương án 2: Telegraf local + OEM + MCP + Hermes Agent + Splunk (audit)

**Version:** 3.0 — Tách Splunk Enterprise thành VM riêng, chỉ phục vụ audit/alert log
**Quy mô:** 30-100 instance DB (Oracle, Postgres, MySQL, MongoDB, SQL Server)
**Hạ tầng:** On-premise (VMware nội bộ)

---

## 1. Tổng quan luồng

```
Host nhóm 1 — 30-100 DB server (Telegraf local)
  Oracle host (+Telegraf)   Postgres/MySQL/Mongo/SQLServer host (+Telegraf)   ...+N host
        |  push 15s                      |  push 15s
        +----------------+---------------+
                         |
                         v
        +----------------------------------------+
        |  Host nhóm 2 — VM trung tâm              |
        |  Luồng A (webhook)   |  Luồng B (Telegraf)|
        |  Webhook receiver    |  InfluxDB + Loki   |
        |        |             |        |           |
        |        |             |  Job chuẩn hóa     |
        |        |             |        |           |
        |        |             |  DDS DB + META DB  |
        |        |             |        |           |
        |        |             |  MCP server         |
        |        +------+------+        |           |
        |               v               |           |
        |          Hermes Agent <-------+           |
        +----------------|-------------------------+
                         |
            +------------+------------+
            v                          v
      Google Chat                    n8n

Host riêng — OEM
  OEM Metric Alert -> alert_push.sh -> curl POST (webhook, luồng A)

Host riêng — VM-Splunk (audit/alert, tách biệt hoàn toàn)
  HTTP Event Collector (HEC) <- audit log, alert log (từ OEM script)
  Splunk Enterprise (search, lưu trữ, dashboard audit)
  KHÔNG kết nối vào MCP / Hermes — DBA xem trực tiếp khi cần
```

---

## 2. Bốn nhóm host độc lập

| Nhóm | Vai trò | Kết nối với nhóm khác |
|---|---|---|
| Nhóm 1 — DB host (30-100 máy) | Telegraf local push metrics 15s | Push vào VM trung tâm (luồng B) |
| Host riêng — OEM | Theo dõi Oracle từ xa, bắt threshold/lock tức thời | Push webhook vào VM trung tâm (luồng A) và vào VM-Splunk (HEC) |
| Nhóm 2 — VM trung tâm | Storage, chuẩn hóa, MCP, Hermes | Nhận từ DB host + OEM, gửi ra Google Chat/n8n |
| VM-Splunk (mới, tách riêng) | Audit log, alert log — chỉ lưu trữ và search nội bộ | Độc lập hoàn toàn, không kết nối MCP/Hermes |

**Lý do tách Splunk hoàn toàn riêng, không gộp VM trung tâm:**

- Splunk Enterprise cần 8-12 vCPU, 12-16GB RAM riêng — cộng vào VM trung tâm sẽ đẩy tổng lên 14-18 vCPU/24-28GB, quá tải so với 1 VM
- Splunk cần disk I/O liên tục cho indexing — tranh chấp I/O với InfluxDB/DDS DB nếu chạy chung sẽ làm chậm cả hai
- Splunk dùng cho mục đích khác (audit/compliance, DBA tra cứu thủ công) — không cần latency thấp như đường Hermes/MCP, tách biệt giúp đơn giản hóa firewall

---

## 3. Thành phần chi tiết

### 3.1 Host nhóm 1 — DB host với Telegraf local

Giữ nguyên thiết kế trước — mỗi DB host tự cài Telegraf, scrape localhost, push metrics 15s vào InfluxDB trên VM trung tâm. Oracle dùng input plugin exec gọi script SQL*Plus do chưa có input plugin chính thức. Triển khai đồng loạt 30-100 host bằng Ansible playbook.

### 3.2 Host riêng — OEM

OEM Metric Alert trigger ngay khi threshold/lock xảy ra. Script alert_push.sh query v$session join v$sql lấy đủ sid, username, machine, program, blocking_session, sql_text, rồi curl POST thẳng vào webhook receiver trên VM trung tâm, chạy nền để không block OEM.

### 3.3 Host nhóm 2 — VM trung tâm

Hai luồng song song bên trong:

- Luồng A (webhook) — nhận event tức thời từ OEM, forward thẳng vào Hermes Agent, không qua MCP
- Luồng B (Telegraf) — nhận push định kỳ, qua InfluxDB/Loki, job chuẩn hóa cron, DDS DB/META DB, rồi MCP server expose tool cho Hermes

Hermes Agent là điểm hội tụ của cả 2 luồng, gửi kết quả ra Google Chat và n8n.

Resource VM trung tâm: 6 vCPU, 12GB RAM, 250GB SSD, 4 user OS riêng (dds_db, mcp_svc, hermes_svc, root chỉ dùng cài đặt).

### 3.4 VM-Splunk (mới) — audit/alert, tách riêng hoàn toàn

Mục đích duy nhất: lưu trữ audit log và alert log để DBA/security team tra cứu thủ công, phục vụ compliance — không phải dashboard performance, không có AI suggestion, không kết nối Hermes.

Nguồn log đẩy vào Splunk gồm audit log Oracle (alert.log, audit trail nếu bật DB audit), alert log từ OEM (bản sao song song với bản gửi Hermes), và log truy cập/login bất thường từ các DB khác nếu cần audit.

**Cơ chế nhận log — 2 lựa chọn:**

| Lựa chọn | Mô tả | Khi dùng |
|---|---|---|
| Splunk Universal Forwarder | Cài thêm forwarder nhẹ trên từng DB host, gửi file log trực tiếp | Khi cần audit log gốc, không qua trung gian |
| HTTP Event Collector (HEC) | OEM/script gửi thẳng qua HTTP POST tới Splunk HEC endpoint | Khi muốn tận dụng lại script alert_push.sh đã có |

Khuyến nghị dùng HEC cho đơn giản — sửa alert_push.sh thêm 1 lệnh curl thứ hai gửi cùng payload tới Splunk HEC, song song với webhook gửi Hermes. Không cần cài Universal Forwarder trên 30-100 host.

```bash
curl -s -X POST "https://VM_SPLUNK_IP:8088/services/collector" \
  -H "Authorization: Splunk $SPLUNK_HEC_TOKEN" \
  -d "{
    \"event\": {
      \"type\": \"$EVENT_TYPE\",
      \"db\": \"$DB_NAME\",
      \"data\": $(echo "$DATA" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
      \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
    }
  }" &
```

**Resource VM-Splunk (mức audit-only, không phải production search-heavy):**

| Resource | Đề xuất |
|---|---|
| vCPU | 8-12 |
| RAM | 12-16GB |
| Disk | 100-200GB SSD riêng (tùy retention 30-90 ngày) |
| I/O | SSD riêng, không share datastore với VM trung tâm |

Lưu ý license: Splunk Enterprise tính phí theo GB ingest/ngày kể cả self-hosted (trừ bản Free giới hạn 500MB/ngày). Cần ước tính dung lượng audit log/ngày từ 30-100 DB trước khi chọn license tier — chỉ audit/alert nên dung lượng thấp hơn nhiều so với Database Monitoring đầy đủ.

---

## 4. Tổng hợp hạ tầng

| Host | Vai trò | vCPU | RAM | Disk |
|---|---|---|---|---|
| Mỗi DB host (30-100) | + Telegraf local | +0.2 | +100MB | — |
| Host OEM | Theo dõi Oracle, gửi event | đã có sẵn | đã có sẵn | đã có sẵn |
| VM trung tâm | DDS+META+MCP+Hermes+InfluxDB+Loki+webhook | 6 | 12GB | 250GB SSD |
| VM-Splunk (mới) | Audit/alert log, tách riêng | 8-12 | 12-16GB | 100-200GB SSD |

Tổng VM trung tâm cần quản lý: 2 (VM trung tâm + VM-Splunk), cộng với Telegraf rải trên DB host và OEM host có sẵn.

---

## 5. Network & Firewall

| Source | Destination | Port | Lý do |
|---|---|---|---|
| Mỗi DB host (Telegraf) | VM trung tâm | 8086 InfluxDB, 3100 Loki | Push metrics/log định kỳ |
| Oracle host (OEM script) | VM trung tâm | webhook port (vd 8080) | Push alert tức thời — luồng A |
| Oracle host (OEM script) | VM-Splunk | 8088 (HEC) | Push audit log song song, độc lập với Hermes |
| VM trung tâm (job chuẩn hóa) | VM trung tâm nội bộ | — | Pull InfluxDB/Loki vào DDS DB |
| VM trung tâm (Hermes) | Internet | 443 | Google Chat API, Claude/Gemini API |
| DBA/Security team | VM-Splunk | 8000 (Splunk Web UI) | Tra cứu audit log thủ công |
| Admin | VM trung tâm, VM-Splunk | SSH | Quản trị |

Điểm quan trọng: VM-Splunk không có route tới MCP server hoặc Hermes — hoàn toàn độc lập, chỉ nhận dữ liệu một chiều từ OEM qua HEC. Splunk phục vụ con người (DBA tra cứu), Hermes phục vụ AI phân tích tự động.

---

## 6. Checklist triển khai

- [ ] Viết Ansible playbook cài Telegraf cho từng loại DB
- [ ] Viết script oracle_metrics.sh cho Telegraf exec input
- [ ] Dựng VM trung tâm: InfluxDB + Loki + DDS DB + META DB + MCP server + Hermes Agent + webhook receiver
- [ ] Tách user OS riêng trên VM trung tâm
- [ ] Viết lock_detail_capture.sh/alert_push.sh trên host OEM, cấu hình Metric Alert
- [ ] Dựng VM-Splunk riêng — cài Splunk Enterprise, cấu hình HEC endpoint, tạo token
- [ ] Sửa alert_push.sh thêm dòng curl thứ hai gửi song song vào Splunk HEC
- [ ] Ước tính dung lượng ingest/ngày để chọn license Splunk phù hợp
- [ ] Setup Google Chat gateway và n8n cho Hermes
- [ ] Test luồng polling và luồng event đầy đủ
- [ ] Cấp quyền Splunk Web UI cho DBA/security team, xác nhận không có route nào từ Splunk vào MCP/Hermes

---

## 7. Rủi ro và lưu ý

| Rủi ro | Mức độ | Giảm thiểu |
|---|---|---|
| Gộp DDS+MCP+Hermes 1 VM — mất isolation | Trung bình | Tách user OS, MCP chỉ quyền SELECT |
| Telegraf rải 30-100 host — khó đồng bộ | Trung bình | Bắt buộc Ansible |
| Polling 15s bỏ lỡ lock ngắn | Cao nếu chỉ dùng Telegraf | Giữ song song OEM event-driven |
| Splunk license cost vượt dự kiến | Trung bình-Cao | Ước tính ingest/ngày trước, cân nhắc Free tier nếu đủ |
| VM-Splunk cần disk I/O riêng | Trung bình | SSD riêng, không share datastore với VM trung tâm |
| Trùng lặp dữ liệu giữa Hermes và Splunk | Thấp | Chấp nhận được, 2 hệ thống phục vụ 2 mục đích khác nhau

---

## 8. Lab vs Production + As-built (bổ sung so với thiết kế gốc §1-7)

Mục này phản ánh **hiện trạng đã triển khai** và **ràng buộc production** — bổ
sung cho phần thiết kế gốc ở trên (giữ nguyên).

### 8.1 Khác biệt Lab ↔ Production

| Hạng mục | Lab (hiện tại) | Production |
|---|---|---|
| LLM | Model nội bộ qua endpoint OpenAI-compatible (`provider: custom`) | **LLM local** on-prem (bắt buộc, không gọi API ngoài) |
| Egress internet | Hermes POST thẳng `chat.googleapis.com:443` | **Chỉ mở proxy đi Google Chat**; không có internet chung |
| Google Chat auth | Incoming webhook URL của space | Incoming webhook **qua proxy** (biến `HTTPS_PROXY`) |

→ **Sửa lại §5 (Firewall):** dòng "VM trung tâm (Hermes) → Internet 443 →
Claude/Gemini API" **không áp dụng**. Thực tế:
- Hermes → **LLM local** (nội bộ, không ra internet).
- Hermes/plugin → **HTTP(S) proxy** → Google Chat (đường egress DUY NHẤT).
  `gchat_webhook` plugin và `gchat_send.sh` đều tôn trọng biến `HTTPS_PROXY`/
  `https_proxy`, nên chỉ cần set proxy trong env của gateway/service.

### 8.2 Thành phần đã dựng nhưng thiếu trong thiết kế gốc

- **Masking tại nguồn** — `oem-host/scripts/redact.py` che IP/host/domain/secret
  **trước khi rời** DB/OEM host. Agent và LLM chỉ thấy placeholder. (Thiết kế
  gốc không đề cập — đây là control bắt buộc cho dữ liệu nhạy cảm.)
- **Google Chat delivery** — không dùng plugin Google Chat native của Hermes
  (cần GCP project + Pub/Sub). Thay bằng **incoming webhook + platform plugin
  `gchat_webhook`** (send-only, `deliver: gchat_webhook`, full text, tất định).
- **Skills Oracle** — `alert-triage`, `oracle-rca`, `awr-summary`
  (agentskills.io) là nội dung phân tích của Hermes ở Luồng A.
- **MCP as-built** — FastMCP streamable-HTTP tại `127.0.0.1:9000`, 4 tool
  read-only (`list_instances`, `recent_metrics`, `recent_events`,
  `incident_history`), chạy user `mcp_svc`, kết nối Postgres bằng role
  SELECT-only `mcp_ro`.
- **Store as-built** — PostgreSQL 17, DB `dds` (metric_rollup/db_event/incident)
  + `meta` (db_instance/metric_catalog); InfluxDB 2 (`central`/`metrics` 30d);
  Loki. Chi tiết vận hành: `central-vm/README.md`.
- **Không dùng Docker** — cài native, mỗi service một OS user + systemd.

### 8.3 Còn trong thiết kế nhưng chưa dựng
Splunk VM (khoán pha sau), n8n (off-host, mới scaffold), Telegraf trên 30-100
DB host (mới có Ansible scaffold), và `alert_push.sh` join `v$session`×`v$sql`
lấy `sql_text` (hiện `check_session.sh` mới lấy blocking tree + locked objects).
