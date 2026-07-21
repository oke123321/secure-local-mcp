# Secure Local MCP Agent (Engineering Edition)

[![CI](https://github.com/oke123321/secure-local-mcp/actions/workflows/python-app.yml/badge.svg)](https://github.com/oke123321/secure-local-mcp/actions/workflows/python-app.yml)

*[Đọc bản tiếng Việt](README.vi.md)*

> A Software Engineer AI Agent system that is 100% offline, secure, and directly interacts with your personal computer via the MCP (Model Context Protocol).

---

## 🎯 The Problem Solved

Current Cloud AIs pose a risk of source code data leaks and cannot directly interact with your local operating system.
This project builds a personal AI running **100% offline (Native)** on Windows, capable of reading/analyzing your project's source code, as well as executing real system commands (like `ping`, `ipconfig`, `dir`) without being restricted by virtualization layers (Docker).

---

## 🏗️ System Architecture (Native Mode)

```text
my_notes/ (Notes) & project_context/ (Source Code)
                        │
                        ▼
src/indexer.py ──── SQLite FTS5 ──── Scan & Index Code/Text
                        │
                        ▼
src/server.py ───── FastMCP ──────── 5 Tools (list, read, search, write, execute_command)
                        │
                        ▼ (stdio / JSON-RPC)
src/ui.py ───────── Streamlit ────── Visual Web Interface (Transparent Tool execution flow)
                        │
                        ▼
Ollama (Gemma4/Qwen) / Any Local LLM
```

---

## ✨ Highlight Features

| Feature | Details |
|-----------|---------|
| **Codebase Indexing** | SQLite FTS5 reads and indexes a variety of programming languages (`.py`, `.js`, `.json`, `.cpp`, `.go`...) while skipping binary files. Blazing fast **O(log N)** speed. |
| **Native OS Commands** | Allows the AI to execute Terminal (Powershell/CMD) commands on the actual Windows machine to query the network or system. |
| **Transparent Web UI** | Every tool execution (reading files, running network commands) is displayed in detail as an Expander block, hiding nothing. |
| **100% Offline & Un-sandboxed** | No Docker is used to avoid network isolation. Data never leaves your machine. |
| **Directory Traversal Protection** | Blocks payloads like `../../etc/passwd`. The AI is strictly restricted to operations within the `my_notes` and `project_context` directories. |

---

## 🚀 Installation & Usage (1-Click)

The system is designed to run directly on Windows (Native) to fully utilize the operating system's capabilities and permissions.

**Requirements:**
- **Python 3.10+** installed (with PATH configured).
- **Ollama** installed and running on the default port (`http://localhost:11434`).

**How to run:**
Simply double-click the **`start.bat`** file. 
The script will automatically:
1. Create a virtual environment (venv).
2. Install the necessary dependencies (`pip install`).
3. Open the Web UI app (Streamlit) in your browser at `http://localhost:8501`.

---

## 🛡️ Security Mechanisms

The system applies a robust protection layer against **Directory Traversal Attacks (CWE-22)**:
It utilizes `resolve()` and `is_relative_to()` to ensure that the read/write paths absolutely cannot escape the 2 permitted root directories (`my_notes` and `project_context`).

---

## 📁 Project Structure

```text
secure-local-mcp/
├── my_notes/               # Personal notes repo (.md, .txt)
├── project_context/        # Project source code for AI analysis (.py, .js, .json,...)
├── src/
│   ├── server.py           # FastMCP Server (Tool declarations)
│   ├── indexer.py          # SQLite FTS5 Indexing Engine (Handles Text & Code)
│   └── ui.py               # Streamlit Web Chat Interface
├── start.bat               # Windows (Native) automated startup script
├── requirements.txt
└── README.md
```
