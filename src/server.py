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
from indexer import NoteIndexer

# ─── Cấu hình đường dẫn ───────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent.resolve()
NOTES_DIR = BASE_DIR / "my_notes"
NOTES_DIR.mkdir(exist_ok=True)

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ─── Khởi tạo FTS5 Indexer (chạy một lần khi server boot) ───────────────────
DB_PATH = DATA_DIR / ".mcp_index.db"
indexer = NoteIndexer(notes_dir=NOTES_DIR, db_path=str(DB_PATH))

# ─── Khởi tạo FastMCP Server ─────────────────────────────────────────────────
mcp = FastMCP(
    name="secure-local-mcp",
    instructions=(
        "Bạn là trợ lý AI tích hợp với hệ thống ghi chú cá nhân. "
        "Sử dụng các tools để tìm kiếm, đọc và ghi chú nội bộ. "
        "Không được truy cập bất kỳ file nào ngoài thư mục my_notes."
    ),
)

# ─── Watchdog: File System Event Handler ──────────────────────────────────────
class NotesEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            logger.info(f"Phát hiện file mới: {event.src_path}. Đang reindex...")
            indexer.upsert_file(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            logger.info(f"Phát hiện file thay đổi: {event.src_path}. Đang cập nhật index...")
            indexer.upsert_file(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            logger.info(f"Phát hiện file bị xóa: {event.src_path}. Đang xóa khỏi index...")
            indexer.remove_file(event.src_path)

def start_watchdog():
    observer = Observer()
    observer.schedule(NotesEventHandler(), str(NOTES_DIR), recursive=True)
    observer.daemon = True
    observer.start()
    logger.info(f"Watchdog đã khởi động, theo dõi thư mục: {NOTES_DIR}")


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
    # Giữ nguyên cấu trúc thư mục con do LLM truyền vào (vd: project_A/todo.md)
    # Hàm resolve() sẽ trả về đường dẫn tuyệt đối
    resolved = (NOTES_DIR / filename).resolve()

    # Kiểm tra kép: đường dẫn phải nằm hoàn toàn trong NOTES_DIR
    # Chặn các payload như ../../etc/passwd
    if not resolved.is_relative_to(NOTES_DIR.resolve()):
        raise PermissionError(
            f"🔒 SECURITY ALERT: Directory Traversal bị chặn! "
            f"Đường dẫn '{filename}' không hợp lệ."
        )

    return resolved


# ─── Tool 1: list_notes ───────────────────────────────────────────────────────
@mcp.tool()
def list_notes() -> str:
    """
    Liệt kê danh sách tất cả các file ghi chú hiện có.

    Returns:
        Chuỗi liệt kê tên file, mỗi file một dòng.
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
    Đọc nội dung chi tiết của một file ghi chú cụ thể.

    Args:
        filename: Tên file cần đọc (ví dụ: project_notes.md).

    Returns:
        Nội dung đầy đủ của file.

    Raises:
        PermissionError: Nếu phát hiện Directory Traversal.
        FileNotFoundError: Nếu file không tồn tại.
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
    Tìm kiếm từ khóa trong toàn bộ kho ghi chú.

    Sử dụng SQLite FTS5 Inverted Index để tìm kiếm với tốc độ O(log N),
    nhanh hơn hàng trăm lần so với đọc file tuần tự.

    Args:
        query: Từ khóa hoặc cụm từ cần tìm.

    Returns:
        Danh sách kết quả kèm đoạn trích dẫn (snippet) chứa từ khóa.
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
    Tạo mới hoặc cập nhật một file ghi chú.

    Args:
        filename: Tên file cần tạo/cập nhật (ví dụ: meeting_notes.md).
        content: Nội dung ghi chú theo định dạng Markdown.

    Returns:
        Thông báo xác nhận thành công.

    Raises:
        PermissionError: Nếu phát hiện Directory Traversal.
        ValueError: Nếu filename chứa ký tự không hợp lệ.
    """
    # Validate: chỉ cho phép file .md
    if not filename.endswith(".md"):
        raise ValueError(f"⚠️ Chỉ hỗ trợ file .md. Nhận được: '{filename}'")

    file_path = _resolve_safe_path(filename)
    
    # Tạo sẵn thư mục cha nếu file nằm trong sub-folder
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_path.write_text(content, encoding="utf-8")

    # Chỉ cập nhật duy nhất file này vào Index, KHÔNG quét lại cả thư mục
    indexer.upsert_file(file_path)

    return f"✅ Đã lưu ghi chú thành công: '{filename}' ({len(content)} ký tự)"


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Secure Local MCP Server đang khởi động...")
    logger.info(f"Thư mục ghi chú: {NOTES_DIR}")
    logger.info(f"Đã lập chỉ mục: {len(indexer.list_files())} file")
    
    # Chạy Watchdog song song
    start_watchdog()
    
    # Khởi chạy MCP server
    mcp.run(transport="stdio")
