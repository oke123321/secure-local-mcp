"""
Phase 2: FastMCP Server
========================
MCP Server sử dụng FastMCP framework để expose 4 Tools cốt lõi.
Giao tiếp qua giao thức JSON-RPC trên transport stdio (chuẩn MCP).
"""
import os
import sys
import logging
import threading
import subprocess
import re
from pathlib import Path
from fastmcp import FastMCP
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ─── Cấu hình Enterprise Logging ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler("server.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("SecureMCP")

# Import indexer từ cùng thư mục
sys.path.insert(0, str(Path(__file__).parent))
from indexer import NoteIndexer, SUPPORTED_EXTS

# ─── Cấu hình đường dẫn ───────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent.resolve()
NOTES_DIR = BASE_DIR / "my_notes"
NOTES_DIR.mkdir(exist_ok=True)

PROJECT_DIR = BASE_DIR / "project_context"
PROJECT_DIR.mkdir(exist_ok=True)

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ─── Khởi tạo FTS5 Indexer (chạy một lần khi server boot) ───────────────────
DB_PATH = DATA_DIR / ".mcp_index.db"
indexer = NoteIndexer(base_dir=BASE_DIR, scan_dirs=[NOTES_DIR, PROJECT_DIR], db_path=str(DB_PATH))

# ─── Khởi tạo FastMCP Server ─────────────────────────────────────────────────
mcp = FastMCP(
    name="secure-local-mcp",
    instructions=(
        "Bạn là một trợ lý kỹ sư phần mềm offline. "
        "Hãy sử dụng các công cụ để đọc, tìm kiếm tài liệu và mã nguồn trong dự án, hoặc tạo ghi chú. "
        "Thư mục làm việc gồm my_notes (ghi chú) và project_context (mã nguồn). "
        "Luôn truyền filepath có chứa tên thư mục (ví dụ: my_notes/todo.md hay project_context/main.py). "
        "Bạn có quyền thực thi lệnh quản trị hệ thống bằng execute_command (đã được giới hạn whitelist)."
    ),
)

# ─── Watchdog: File System Event Handler ──────────────────────────────────────
class NotesEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and Path(event.src_path).suffix.lower() in SUPPORTED_EXTS:
            logger.info(f"New file detected: {event.src_path}. Reindexing...")
            indexer.upsert_file(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and Path(event.src_path).suffix.lower() in SUPPORTED_EXTS:
            logger.info(f"File modified: {event.src_path}. Updating index...")
            indexer.upsert_file(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and Path(event.src_path).suffix.lower() in SUPPORTED_EXTS:
            logger.info(f"File deleted: {event.src_path}. Removing from index...")
            indexer.remove_file(event.src_path)

def start_watchdog():
    observer = Observer()
    observer.schedule(NotesEventHandler(), str(NOTES_DIR), recursive=True)
    observer.schedule(NotesEventHandler(), str(PROJECT_DIR), recursive=True)
    observer.daemon = True
    observer.start()
    logger.info(f"Watchdog started, monitoring: {NOTES_DIR} and {PROJECT_DIR}")


def _resolve_safe_path(filename: str) -> Path:
    """
    Kiểm tra bảo mật chống Directory Traversal Attack.

    Chuẩn hóa đường dẫn và kiểm tra xem file có nằm trong
    thư mục my_notes không. Chặn mọi payload như ../../etc/passwd.

    Args:
        filename: Tên file cần kiểm tra.

    Returns:
        Path tuyệt đối hợp lệ.

    Raises:
        PermissionError: Nếu phát hiện directory traversal attack.
    """
    # Giữ nguyên cấu trúc thư mục con do LLM truyền vào (vd: project_context/main.py)
    # Hàm resolve() sẽ trả về đường dẫn tuyệt đối
    resolved = (BASE_DIR / filename).resolve()

    # Kiểm tra kép: đường dẫn phải nằm hoàn toàn trong NOTES_DIR hoặc PROJECT_DIR
    # Chặn các payload như ../../etc/passwd
    if not (resolved.is_relative_to(NOTES_DIR.resolve()) or resolved.is_relative_to(PROJECT_DIR.resolve())):
        raise PermissionError(
            f"🔒 SECURITY ALERT: Directory Traversal bị chặn! "
            f"Đường dẫn '{filename}' không hợp lệ."
        )

    return resolved


# ─── Tool 1: list_notes ───────────────────────────────────────────────────────
@mcp.tool()
def list_notes() -> str:
    """
    List all indexed files (notes and project source code).
    Use this to show the user what files are available.

    Returns:
        A string listing all filenames, one per line.
    """
    files = indexer.list_files()

    if not files:
        return "📭 Thư mục ghi chú hiện đang trống."

    file_list = "\n".join(f"  📄 {f}" for f in sorted(files))
    return f"📚 Danh sách ghi chú ({len(files)} file):\n{file_list}"


# ─── Tool 2: read_note ────────────────────────────────────────────────────────
@mcp.tool()
def read_note(filename: str) -> str:
    """
    Read the full content of a specific file (note or source code).
    Use this when the user asks to read, view, or explain the contents of a specific file.

    Args:
        filename: Path to the file including its directory prefix, e.g. "my_notes/todo.md" or "project_context/main.py".

    Returns:
        Full content of the file.
    """
    file_path = _resolve_safe_path(filename)

    if not file_path.exists():
        return f"❌ Không tìm thấy file: '{filename}'. Hãy dùng list_notes() để xem danh sách."

    content = file_path.read_text(encoding="utf-8")
    return f"📄 **{filename}**\n{'─' * 40}\n{content}"


# ─── Tool 3: search_notes ─────────────────────────────────────────────────────
@mcp.tool()
def search_notes(query: str) -> str:
    """
    Search for keywords across all indexed files (notes AND project source code).
    Use this when the user asks to find something in their notes or project, or asks questions like
    "where is function X?", "which files mention Y?", "find me something about Z".
    Uses SQLite FTS5 full-text search for O(log N) speed.

    Args:
        query: The keyword or phrase to search for.

    Returns:
        A list of matching files with relevant text snippets.
    """
    if not query.strip():
        return "⚠️ Vui lòng nhập từ khóa cần tìm."

    results = indexer.search(query)

    if not results:
        return f"🔍 Không tìm thấy kết quả nào cho: '{query}'"

    output_lines = [f"🔍 **Kết quả tìm kiếm cho '{query}'** ({len(results)} file):\n"]
    for i, result in enumerate(results, 1):
        output_lines.append(
            f"{i}. 📄 **{result.filename}** — *{result.title}*\n"
            f"   > {result.snippet}\n"
        )

    return "\n".join(output_lines)


# ─── Tool 4: write_note ───────────────────────────────────────────────────────
@mcp.tool()
def write_note(filename: str, content: str) -> str:
    """
    Create or update a file in the notes directory.
    Use this when the user asks to save, write, create, or update a note or document.

    Args:
        filename: File path including directory prefix, e.g. "my_notes/meeting.md".
            Supported formats: .md, .txt, .py, .js, .json, .yaml, .yml, .ini, .csv, .log
        content: The content to write (Markdown or plain text).

    Returns:
        Success confirmation message.
    """
    # Validate: chỉ cho phép các định dạng được hỗ trợ
    path_obj = Path(filename)
    if path_obj.suffix.lower() not in SUPPORTED_EXTS:
        raise ValueError(f"⚠️ Định dạng file không được hỗ trợ. Nhận được: '{filename}'")

    file_path = _resolve_safe_path(filename)
    
    # Tạo sẵn thư mục cha nếu file nằm trong sub-folder
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_path.write_text(content, encoding="utf-8")

    # Chỉ cập nhật duy nhất file này vào Index, KHÔNG quét lại cả thư mục
    indexer.upsert_file(file_path)

    return f"✅ Đã lưu ghi chú thành công: '{filename}' ({len(content)} ký tự)"


# ─── Security Firewall cho System Commands ────────────────────────────────────
SAFE_COMMANDS = ['ping', 'ipconfig', 'arp', 'nslookup', 'tracert', 'tasklist', 'systeminfo', 'hostname', 'whoami', 'getmac', 'netstat', 'nbtstat', 'pathping', 'curl']
DANGEROUS_COMMANDS = ['netsh', 'route', 'net', 'wmic']
FORBIDDEN_CHARS = ['&', '|', ';', '>', '<', '$', '`', '\n']

def check_command_safety(command: str) -> tuple[bool, str]:
    """Kiểm tra whitelist và command injection."""
    if not command or not command.strip():
        return False, "Lệnh trống."
    
    # Kiểm tra ký tự độc hại
    for char in FORBIDDEN_CHARS:
        if char in command:
            return False, f"Lệnh chứa ký tự cấm: '{char}'. Khả năng Command Injection."
            
    parts = command.strip().split()
    base_command = parts[0].lower()
    
    # Ở Windows, đôi khi base_command có đuôi .exe
    if base_command.endswith('.exe'):
        base_command = base_command[:-4]
        
    if base_command in SAFE_COMMANDS:
        return True, "Safe"
    elif base_command in DANGEROUS_COMMANDS:
        return True, "Dangerous"
    else:
        return False, f"Lệnh '{base_command}' không nằm trong Whitelist."


# ─── Tool 5: execute_command ──────────────────────────────────────────────────
@mcp.tool()
def execute_command(command: str) -> str:
    """
    Execute a SAFE system/network command and return its output.
    
    ALLOWED SAFE COMMANDS: ping, ipconfig, arp, nslookup, tracert, tasklist, systeminfo, hostname, whoami, getmac, netstat, nbtstat, pathping, curl
    
    If the user asks for dangerous commands (netsh, route, net, wmic), DO NOT use this tool.
    Use execute_dangerous_command instead, after getting user permission.
    """
    is_valid, status = check_command_safety(command)
    if not is_valid:
        return f"🚫 SECURITY ALERT: Từ chối quyền - {status}"
        
    if status == "Dangerous":
        return f"⚠️ CẢNH BÁO BẢO MẬT: '{command}' là lệnh nguy hiểm. BẠN PHẢI HỎI XIN PHÉP NGƯỜI DÙNG. Nếu người dùng ĐỒNG Ý, hãy dùng công cụ `execute_dangerous_command` để chạy."
        
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout if result.stdout else result.stderr
        return f"✅ Lệnh chạy thành công:\n{output}"
    except subprocess.TimeoutExpired:
        return "❌ Lỗi: Lệnh bị timeout (vượt quá giới hạn 30 giây)."
    except Exception as e:
        return f"❌ Lỗi thực thi: {str(e)}"


# ─── Tool 6: execute_dangerous_command ────────────────────────────────────────
@mcp.tool()
def execute_dangerous_command(command: str) -> str:
    """
    Execute a DANGEROUS system command (netsh, route, net, wmic).
    
    CRITICAL RULE: You MUST ask the user for explicit permission BEFORE calling this tool.
    Explain what the command does and wait for their 'Yes' or 'Đồng ý'.
    Only call this tool AFTER the user has approved.
    """
    is_valid, status = check_command_safety(command)
    if not is_valid:
        return f"🚫 SECURITY ALERT: Từ chối quyền - {status}"
        
    if status != "Dangerous":
        return "Lệnh này an toàn, hãy dùng execute_command thay thế."
        
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout if result.stdout else result.stderr
        return f"✅ Lệnh NGUY HIỂM đã chạy thành công:\n{output}"
    except subprocess.TimeoutExpired:
        return "❌ Lỗi: Lệnh bị timeout (vượt quá giới hạn 30 giây)."
    except Exception as e:
        return f"❌ Lỗi thực thi: {str(e)}"


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Secure Local MCP Server is starting...")
    logger.info(f"Notes directory: {NOTES_DIR}")
    logger.info(f"Indexed files: {len(indexer.list_files())}")
    
    # Chạy Watchdog song song
    start_watchdog()
    
    # Khởi chạy MCP server
    mcp.run(transport="stdio")
