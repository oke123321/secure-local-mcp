import streamlit as st
from pathlib import Path
from indexer import NoteIndexer

# Tối ưu RAM: Khởi tạo db trên disk thay vì :memory:, cache đối tượng connection
@st.cache_resource
def load_indexer():
    notes_dir = Path(__file__).parent.parent / "my_notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    # Lưu file db xuống disk để không tốn RAM hệ thống
    db_path = Path(__file__).parent.parent / "notes.db"
    return NoteIndexer(notes_dir=notes_dir, db_path=str(db_path))

st.set_page_config(page_title="Local FTS5 Search", page_icon="🔍")

st.title("🔍 Search Engine (FTS5)")
st.caption("Tìm kiếm siêu tốc độ qua SQLite Inverted Index")

indexer = load_indexer()

query = st.text_input("Nhập từ khóa tìm kiếm...", placeholder="Gõ gì đó...")

if query:
    results = indexer.search(query)
    if results:
        st.success(f"⚡ Đã tìm thấy {len(results)} kết quả")
        for res in results:
            st.subheader(res.title)
            st.caption(f"📄 `{res.filename}`")
            # Highlight từ khóa (SQLite FTS5 trả về '[' và ']')
            snippet = res.snippet.replace('[', '<mark>').replace(']', '</mark>')
            st.markdown(f"> {snippet}", unsafe_allow_html=True)
            st.divider()
    else:
        st.warning("Không có kết quả nào phù hợp.")
