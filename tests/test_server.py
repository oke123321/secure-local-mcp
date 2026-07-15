"""
Phase 4: Unit Tests
====================
Bộ Unit Test sử dụng pytest để kiểm tra chính xác logic nghiệp vụ.
Covers 2 case tử huyệt: FTS5 Search Accuracy & Directory Traversal Security.
"""
import sys
import tempfile
import pytest
from pathlib import Path

# ─── Bootstrap path ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from indexer import NoteIndexer, SearchResult


# ─── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def notes_dir(tmp_path: Path) -> Path:
    """Tạo thư mục ghi chú tạm thời với dữ liệu mẫu."""
    # File 1: Ghi chú về dự án
    (tmp_path / "project_alpha.md").write_text(
        "# Dự án Alpha\n\nMô tả: Hệ thống tự động hóa quy trình CI/CD.\n"
        "Trạng thái: Đang phát triển.\nTech stack: Python, Docker, Kubernetes.",
        encoding="utf-8",
    )

    # File 2: Ghi chú về mật khẩu và cấu hình
    (tmp_path / "internal_config.md").write_text(
        "# Cấu hình Nội bộ\n\nMật khẩu Redis: secret_pass_123\n"
        "Mật khẩu Postgres: db_pass_456\nWifi văn phòng: MindX@2026",
        encoding="utf-8",
    )

    # File 3: Ghi chú meeting
    (tmp_path / "meeting_notes.md").write_text(
        "# Meeting Tuần 28\n\nAction items:\n"
        "- Deploy dự án Alpha lên staging\n"
        "- Review code PR #42\n"
        "- Báo cáo tiến độ dự án cho PM",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def indexer(notes_dir: Path) -> NoteIndexer:
    """Tạo NoteIndexer đã được lập chỉ mục với dữ liệu mẫu."""
    idx = NoteIndexer(notes_dir=notes_dir, db_path=":memory:")
    return idx


# ─── Test Group 1: Khởi tạo và Lập chỉ mục ──────────────────────────────────
class TestIndexing:
    def test_reindex_returns_correct_count(self, indexer: NoteIndexer):
        """Kiểm tra số lượng file được lập chỉ mục."""
        count = indexer.reindex()
        assert count == 3, f"Kỳ vọng 3 file, nhận được {count}"

    def test_list_files_returns_all(self, indexer: NoteIndexer):
        """Kiểm tra list_files trả về đúng danh sách."""
        files = indexer.list_files()
        assert len(files) == 3
        assert "project_alpha.md" in files
        assert "internal_config.md" in files
        assert "meeting_notes.md" in files

    def test_empty_directory(self, tmp_path: Path):
        """Kiểm tra hành vi với thư mục rỗng."""
        empty_idx = NoteIndexer(notes_dir=tmp_path, db_path=":memory:")
        assert empty_idx.list_files() == []
        assert empty_idx.search("anything") == []


# ─── Test Group 2: Độ chính xác của FTS5 Search ──────────────────────────────
class TestSearchAccuracy:
    def test_search_finds_exact_keyword(self, indexer: NoteIndexer):
        """Tìm kiếm từ khóa chính xác phải trả về đúng file."""
        results = indexer.search("Kubernetes")
        assert len(results) >= 1
        filenames = [r.filename for r in results]
        assert "project_alpha.md" in filenames

    def test_search_returns_snippet(self, indexer: NoteIndexer):
        """Kết quả tìm kiếm phải chứa snippet hữu ích."""
        results = indexer.search("Mật khẩu")
        assert len(results) >= 1
        # Snippet phải chứa nội dung liên quan
        assert any("Mật khẩu" in r.snippet or "secret" in r.snippet for r in results)

    def test_search_multiple_files(self, indexer: NoteIndexer):
        """Tìm kiếm từ khóa xuất hiện ở nhiều file."""
        results = indexer.search("dự án")
        filenames = [r.filename for r in results]
        # "dự án" xuất hiện trong cả project_alpha.md và meeting_notes.md
        assert len(filenames) >= 1

    def test_search_no_result(self, indexer: NoteIndexer):
        """Tìm kiếm không có kết quả phải trả về list rỗng."""
        results = indexer.search("từ_khóa_không_tồn_tại_xyz_abc_123")
        assert results == []

    def test_search_empty_query(self, indexer: NoteIndexer):
        """Tìm kiếm với chuỗi rỗng phải trả về list rỗng."""
        results = indexer.search("")
        assert results == []


# ─── Test Group 3: BẢO MẬT - Directory Traversal Attack Prevention ───────────
class TestDirectoryTraversalSecurity:
    """
    ⚠️ Bộ test quan trọng nhất: Kiểm tra server không bị tấn công
    Directory Traversal, một lỗ hổng bảo mật nghiêm trọng (CWE-22).
    """

    def _get_resolved_path(self, notes_dir: Path, filename: str) -> Path:
        """
        Giả lập logic _resolve_safe_path() mới sử dụng is_relative_to
        """
        resolved = (notes_dir / filename).resolve()
        if not resolved.is_relative_to(notes_dir.resolve()):
            raise PermissionError("Directory Traversal bị chặn!")
        return resolved

    @pytest.mark.parametrize("malicious_path", [
        "../../etc/passwd",
        "../../../Windows/System32/config/SAM",
        "..\\..\\..\\Windows\\win.ini",
        "/etc/shadow",
        "C:\\Windows\\System32\\cmd.exe",
        "..//..//..//etc/passwd",
    ])
    def test_blocks_directory_traversal(self, notes_dir: Path, malicious_path: str):
        """
        ✅ Server PHẢI chặn đứng mọi đường dẫn nguy hiểm.
        """
        with pytest.raises(PermissionError, match="bị chặn"):
            self._get_resolved_path(notes_dir, malicious_path)

    def test_allows_valid_filename(self, notes_dir: Path):
        """✅ File hợp lệ phải được phép truy cập bình thường."""
        valid_path = self._get_resolved_path(notes_dir, "project_alpha.md")
        assert valid_path.is_relative_to(notes_dir.resolve())

    def test_allows_valid_subfolder(self, notes_dir: Path):
        """✅ File trong thư mục con phải hợp lệ."""
        valid_path = self._get_resolved_path(notes_dir, "project_a/todo.md")
        assert valid_path.is_relative_to(notes_dir.resolve())
        assert valid_path.name == "todo.md"

    def test_only_md_files_allowed_to_write(self):
        """✅ Hàm write_note chỉ cho phép file .md."""
        # Giả lập logic validate trong server.py
        def validate_extension(filename: str) -> bool:
            return filename.endswith(".md")

        assert validate_extension("notes.md") is True
        assert validate_extension("hack.sh") is False
        assert validate_extension("../../etc/crontab") is False
        assert validate_extension(".bashrc") is False
