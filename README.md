# Secure Local MCP Server

[![CI: Passing](https://github.com/oke123321/secure-local-mcp/actions/workflows/python-app.yml/badge.svg)](https://github.com/oke123321/secure-local-mcp/actions)

> **3-Day Fresher Engineering Automation Challenge**  
> Một hệ thống AI Agent hoàn toàn offline, bảo mật, và tối ưu hóa hiệu năng, xây dựng trên nền tảng Model Context Protocol (MCP).

---

## 🎯 Vấn đề đã giải quyết

Các kỹ sư phần mềm mất trung bình **15-20 phút/ngày** chỉ để tìm kiếm thông tin trong hàng chục file ghi chú rải rác. Paste dữ liệu nội bộ lên ChatGPT/Claude Web là **rủi ro bảo mật nghiêm trọng (Data Leak)**.

Dự án này xây dựng một AI cá nhân chạy **100% offline**, giao tiếp trực tiếp với kho ghi chú nội bộ thông qua giao thức **MCP (Model Context Protocol)**.

---

## 🏗️ Kiến trúc hệ thống

```
my_notes/ (Kho dữ liệu)
     │
     ▼
src/indexer.py ──── SQLite FTS5 ──── O(log N) search
     │
     ▼
src/server.py ───── FastMCP ──────── 4 Tools: list/read/search/write
     │
     ▼ (stdio / JSON-RPC)
Claude Desktop / Any MCP Client
```

---

## ✨ Tính năng nổi bật

| Tính năng | Chi tiết |
|-----------|---------|
| **SQLite FTS5 Search** | Tìm kiếm toàn văn với Inverted Index, tốc độ **O(log N)** |
| **Directory Traversal Protection** | Chặn 100% payload `../../etc/passwd` |
| **100% Offline** | Không gọi bất kỳ API Cloud nào. Dữ liệu không bao giờ rời máy |
| **MCP Standard** | Tuân thủ chuẩn giao thức JSON-RPC của Model Context Protocol |
| **Dockerized** | Đóng gói sẵn, chạy được trên mọi môi trường |
| **Unit Tested** | 11+ test cases bao gồm FTS5 accuracy & security tests |

---

## 🚀 Cài đặt và chạy

Hệ thống cung cấp sẵn `Makefile` chuẩn DevOps để tự động hóa toàn bộ quá trình khởi chạy. Không cần nhớ nhiều lệnh dài dòng!

### 1. Cài đặt dependencies và chạy Unit Tests

```bash
make install
make test
```
*Kết quả mong đợi: **17/17 tests PASSED** ✅*

### 2. Chạy MCP Server trực tiếp

```bash
make run
```
*Server sẽ tự động nạp Database và chạy Hot-Reload (Watchdog) giám sát thư mục.*

### 3. Tích hợp vào Claude Desktop

Mở file cấu hình Claude Desktop và thêm nội dung từ `claude_config.json`:
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS/Linux:** `~/.config/claude/claude_desktop_config.json`

### 4. Chạy trong Docker

```bash
make docker-build
make docker-run
```

---

## 🛡️ Bảo mật

Hệ thống áp dụng 2 lớp bảo vệ chống **Directory Traversal Attack (CWE-22)**:

1. **Resolve path:** Dùng `resolve()` để lấy đường dẫn tuyệt đối cuối cùng.
2. **Strict bounds check:** Dùng `is_relative_to(NOTES_DIR)` để đảm bảo đường dẫn không thoát ra khỏi thư mục gốc, đồng thời vẫn hỗ trợ đọc/ghi an toàn trong các thư mục con (sub-folders).

---

## 📁 Cấu trúc dự án

```
secure-local-mcp/
├── my_notes/               # Kho ghi chú cá nhân (.md files)
├── src/
│   ├── server.py           # FastMCP Server (4 Tools)
│   └── indexer.py          # SQLite FTS5 Indexing Engine
├── tests/
│   └── test_server.py      # Unit Tests (pytest)
├── Dockerfile
├── requirements.txt
├── claude_config.json
└── README.md
```

---

## 💡 Reflection - Bài học từ dự án

1. **SQLite đã có sẵn và cực kỳ mạnh mẽ.** Không cần cài thêm vector database hay Elasticsearch cho các bài toán tìm kiếm tài liệu quy mô nhỏ-vừa. FTS5 xử lý được hàng triệu bản ghi.
2. **MCP sẽ là "USB-C của ngành AI".** Kiến trúc tách bạch giữa Data Layer (server.py) và Reasoning Layer (LLM) giúp hệ thống có thể thay đổi model AI mà không cần viết lại logic backend.
3. **Bảo mật không phải là tính năng bổ sung.** Directory Traversal phải được bảo vệ từ ngày đầu, không phải vá víu sau.
