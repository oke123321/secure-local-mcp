"""
Phase 1: SQLite FTS5 Indexing Engine
=====================================
Sử dụng SQLite FTS5 (Full-Text Search 5) để lập chỉ mục tìm kiếm.
Thay thế hoàn toàn os.walk() tuần tự O(N×M) bằng Inverted Index O(log N).
"""
import sqlite3
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchResult:
    """Kết quả trả về từ một truy vấn tìm kiếm."""
    filename: str
    title: str
    snippet: str
    rank: float


class NoteIndexer:
    """
    Engine lập chỉ mục và tìm kiếm ghi chú dựa trên SQLite FTS5.

    FTS5 Virtual Table tạo ra một Inverted Index bên trong SQLite,
    cho phép tìm kiếm toàn văn (full-text search) với tốc độ O(log N)
    thay vì quét từng file tuần tự O(N×M).
    """

    def __init__(self, notes_dir: str | Path, db_path: str = ":memory:"):
        """
        Khởi tạo indexer.

        Args:
            notes_dir: Đường dẫn đến thư mục chứa các file ghi chú.
            db_path: Đường dẫn file SQLite DB.
        """
        self.notes_dir = Path(notes_dir).resolve()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()
        
        # Chỉ reindex nếu DB rỗng
        if self._needs_reindex():
            self.reindex()

    def _needs_reindex(self) -> bool:
        row = self.conn.execute("SELECT COUNT(*) as c FROM notes_fts").fetchone()
        return row["c"] == 0

    def _create_schema(self) -> None:
        """Tạo bảng FTS5 Virtual Table nếu chưa tồn tại."""
        self.conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                filename,
                title,
                content,
                tokenize="unicode61 remove_diacritics 1"
            );
        """)
        self.conn.commit()

    def reindex(self) -> int:
        """
        Quét toàn bộ thư mục my_notes và nạp lại dữ liệu vào FTS5.

        Returns:
            Số lượng file đã được đánh chỉ mục.
        """
        self.conn.execute("DELETE FROM notes_fts")
        indexed_count = 0

        if not self.notes_dir.exists():
            self.conn.commit()
            return 0

        for file_path in self.notes_dir.rglob("*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.strip().splitlines()
                # Lấy dòng đầu tiên có nội dung làm tiêu đề
                title = next(
                    (line.lstrip("# ").strip() for line in lines if line.strip()),
                    file_path.stem
                )
                rel_path = file_path.relative_to(self.notes_dir).as_posix()
                self.conn.execute(
                    "INSERT INTO notes_fts(filename, title, content) VALUES (?, ?, ?)",
                    (rel_path, title, content),
                )
                indexed_count += 1
            except (OSError, UnicodeDecodeError):
                # Bỏ qua file không đọc được
                continue

        self.conn.commit()
        return indexed_count

    def upsert_file(self, file_path: Path | str) -> bool:
        """Chèn hoặc cập nhật một file cụ thể mà không cần quét lại toàn thư mục."""
        path_obj = Path(file_path).resolve()
        if not path_obj.exists() or path_obj.suffix != '.md':
            return False
            
        try:
            rel_path = path_obj.relative_to(self.notes_dir).as_posix()
            content = path_obj.read_text(encoding="utf-8")
            lines = content.strip().splitlines()
            title = next((line.lstrip("# ").strip() for line in lines if line.strip()), path_obj.stem)
            
            # Xóa bản ghi cũ (FTS5 không hỗ trợ UPSERT chuẩn qua rowid nếu cấu trúc phức tạp)
            self.conn.execute("DELETE FROM notes_fts WHERE filename = ?", (rel_path,))
            self.conn.execute(
                "INSERT INTO notes_fts(filename, title, content) VALUES (?, ?, ?)",
                (rel_path, title, content)
            )
            self.conn.commit()
            return True
        except (OSError, UnicodeDecodeError, ValueError):
            return False

    def remove_file(self, file_path: Path | str) -> bool:
        """Xóa một file khỏi CSDL index khi file bị xóa."""
        try:
            path_obj = Path(file_path)
            # Dùng relative_to sẽ throw lỗi nếu file không thuộc notes_dir
            # Nhưng watchdog truyền đường dẫn tuyệt đối, nên ta thử tính toán
            rel_path = path_obj.relative_to(self.notes_dir).as_posix()
            self.conn.execute("DELETE FROM notes_fts WHERE filename = ?", (rel_path,))
            self.conn.commit()
            return True
        except ValueError:
            # File không nằm trong notes_dir
            return False

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """
        Tìm kiếm từ khóa trong tất cả các ghi chú.

        Args:
            query: Từ khóa hoặc cụm từ cần tìm.
            limit: Số kết quả tối đa trả về.

        Returns:
            Danh sách SearchResult được sắp xếp theo độ liên quan (rank).
        """
        if not query or not query.strip():
            return []

        # Escape ký tự đặc biệt của FTS5
        safe_query = query.replace('"', '""')

        try:
            rows = self.conn.execute(
                """
                SELECT
                    filename,
                    title,
                    snippet(notes_fts, 2, '[', ']', '...', 32) AS snippet,
                    rank
                FROM notes_fts
                WHERE notes_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (safe_query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            # Query syntax không hợp lệ, fallback sang LIKE search
            rows = self.conn.execute(
                """
                SELECT filename, title, content AS snippet, 0 AS rank
                FROM notes_fts
                WHERE content LIKE ?
                LIMIT ?
                """,
                (f"%{query}%", limit),
            ).fetchall()

        return [
            SearchResult(
                filename=row["filename"],
                title=row["title"],
                snippet=row["snippet"],
                rank=row["rank"],
            )
            for row in rows
        ]

    def list_files(self) -> list[str]:
        """Trả về danh sách tên file đã được đánh chỉ mục."""
        rows = self.conn.execute("SELECT filename FROM notes_fts").fetchall()
        return [row["filename"] for row in rows]

    def close(self) -> None:
        """Đóng kết nối database."""
        self.conn.close()
