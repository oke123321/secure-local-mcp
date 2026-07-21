# Secure Local MCP Agent (Engineering Edition)

[![CI](https://github.com/oke123321/secure-local-mcp/actions/workflows/python-app.yml/badge.svg)](https://github.com/oke123321/secure-local-mcp/actions/workflows/python-app.yml)

> Một hệ thống AI Agent Kỹ sư Phần mềm hoàn toàn offline, bảo mật, và tương tác trực tiếp với máy tính cá nhân qua giao thức MCP (Model Context Protocol).

---

## 🎯 Vấn đề đã giải quyết

Các Cloud AI hiện tại có nguy cơ lộ lọt dữ liệu mã nguồn (Data Leak) và không thể tương tác trực tiếp với hệ điều hành máy tính của bạn.
Dự án này xây dựng một AI cá nhân chạy **100% offline (Native)** trên Windows, vừa có khả năng đọc/phân tích mã nguồn dự án, vừa có quyền thực thi các lệnh hệ thống thực tế (như \ping\, \ipconfig\, \dir\) mà không bị kìm hãm bởi các lớp áo ảo hóa (Docker).

---

## 🏗️ Kiến trúc hệ thống (Native Mode)

```text
my_notes/ (Ghi chú) & project_context/ (Mã nguồn)
                        │
                        ▼
src/indexer.py ──── SQLite FTS5 ──── Quét & Lập chỉ mục Code/Text
                        │
                        ▼
src/server.py ───── FastMCP ──────── 5 Tools (list, read, search, write, execute_command)
                        │
                        ▼ (stdio / JSON-RPC)
src/ui.py ───────── Streamlit ────── Giao diện Web trực quan (Hiển thị luồng gọi Tool minh bạch)
                        │
                        ▼
Ollama (Gemma4/Qwen) / Any Local LLM
```

---

## ✨ Tính năng nổi bật

| Tính năng | Chi tiết |
|-----------|---------|
| **Codebase Indexing** | SQLite FTS5 đọc và lập chỉ mục hàng loạt ngôn ngữ lập trình (`.py`, `.js`, `.json`, `.cpp`, `.go`...) bỏ qua file nhị phân. Tốc độ **O(log N)**. |
| **Native OS Commands** | Cho phép AI thực thi các lệnh Terminal (Powershell/CMD) trên máy Windows thực tế để tra cứu mạng hoặc hệ thống. |
| **Giao diện Web Minh bạch** | Mọi hành động gọi tool (đọc file, chạy lệnh mạng) đều được hiển thị chi tiết dưới dạng khối Expanders, không giấu giếm. |
| **100% Offline & Un-sandboxed** | Không dùng Docker để tránh bị cô lập hệ thống mạng. Dữ liệu không bao giờ rời máy tính. |
| **Directory Traversal Protection** | Chặn đứng payload `../../etc/passwd`. AI chỉ được phép thao tác trong vùng `my_notes` và `project_context`. |

---

## 🚀 Cài đặt và chạy (Chỉ 1 Click)

Hệ thống được thiết kế để chạy trực tiếp trên Windows (Native) nhằm tận dụng tối đa quyền hạn của hệ điều hành. 

**Yêu cầu:**
- Đã cài đặt **Python 3.10+** (đã cấu hình PATH).
- Đã cài đặt và chạy **Ollama** ở cổng mặc định (`http://localhost:11434`).

**Cách khởi chạy:**
Chỉ cần nhấp đúp chuột vào file **`start.bat`**. 
Script sẽ tự động:
1. Tạo môi trường ảo (venv).
2. Cài đặt các thư viện cần thiết (`pip install`).
3. Mở ứng dụng Web UI (Streamlit) trên trình duyệt tại `http://localhost:8501`.

---

## 🛡️ Cơ chế Bảo mật

Hệ thống áp dụng lớp bảo vệ chống **Directory Traversal Attack (CWE-22)**:
Dùng hàm `resolve()` và `is_relative_to()` để đảm bảo đường dẫn đọc/ghi tuyệt đối không thoát ra khỏi 2 thư mục gốc được cho phép (`my_notes` và `project_context`).

---

## 📁 Cấu trúc dự án

```text
secure-local-mcp/
├── my_notes/               # Kho ghi chú cá nhân (.md, .txt)
├── project_context/        # Mã nguồn dự án để AI phân tích (.py, .js, .json,...)
├── src/
│   ├── server.py           # FastMCP Server (Khai báo Tools)
│   ├── indexer.py          # SQLite FTS5 Indexing Engine (Xử lý cả Text & Code)
│   └── ui.py               # Giao diện Streamlit Web Chat
├── start.bat               # Script khởi động tự động trên Windows (Native)
├── requirements.txt
└── README.md
```
