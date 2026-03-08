import streamlit as st
import tempfile
import shutil
import atexit
import os
import json
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Form Checker",
    page_icon="📋",
    layout="wide",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background-color: #0f0f13; color: #e8e8e8; }
h1,h2,h3 { font-family: 'IBM Plex Mono', monospace !important; color: #f0f0f0 !important; }
.block-container { padding-top: 2rem; max-width: 1300px; }

.app-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border: 1px solid #2a2a4a; border-radius: 12px;
    padding: 2rem 2.5rem; margin-bottom: 2rem;
}
.app-title {
    font-family: 'IBM Plex Mono', monospace; font-size: 2rem;
    font-weight: 600; color: #e0e8ff; margin: 0;
}
.app-subtitle { font-size: 0.9rem; color: #7888aa; margin-top: 0.4rem; font-weight: 300; }

.mode-tab {
    display: inline-block; padding: 6px 18px; border-radius: 6px 6px 0 0;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; font-weight: 600;
    cursor: pointer; border: 1px solid #2a2a4a; border-bottom: none;
    background: #14141e; color: #6878a8;
}
.mode-tab.active { background: #1e2e4e; color: #b0c8e8; border-color: #3a4a7a; }

.badge {
    display: inline-block; padding: 3px 10px; border-radius: 4px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem;
    font-weight: 600; letter-spacing: 0.5px;
}
.badge-3a { background:#1a3a2a; color:#4caf84; border:1px solid #2a5a3a; }
.badge-3b { background:#1a2a3a; color:#4a8fcf; border:1px solid #2a3a5a; }
.badge-3c { background:#2a1a3a; color:#9a6fcf; border:1px solid #3a2a5a; }
.badge-3d { background:#3a2a1a; color:#cf9a4f; border:1px solid #5a3a2a; }
.badge-unknown { background:#2a2a1a; color:#cfcf4f; border:1px solid #4a4a2a; }

.unknown-banner {
    background: #1e1c0a; border: 1px solid #4a4a1a; border-radius: 8px;
    padding: 0.8rem 1.2rem; margin: 0.5rem 0;
}
.unknown-banner-title {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;
    color: #cfcf4f; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.3rem;
}

.dir-box {
    background: #0e1a2e; border: 1px solid #1e3a5f; border-radius: 8px;
    padding: 1rem 1.2rem; margin-bottom: 0.8rem;
}
.dir-stat { font-size: 0.82rem; color: #7898c8; margin-top: 0.4rem; }

.result-block {
    background: #12121c; border: 1px solid #1e2e3e;
    border-radius: 10px; padding: 1.2rem 1.5rem; margin-bottom: 1rem;
}
.check-row {
    display:flex; justify-content:space-between; padding: 5px 0;
    border-bottom: 1px solid #1e1e2e; font-size: 0.88rem;
}
.check-label { color: #8899aa; }
.ok   { color: #4caf84; font-weight: 600; }
.fail { color: #cf4f4f; font-weight: 600; }
.val  { color: #c8c8e8; }

.stButton>button {
    background:#1e3a5f; color:#b0c8e8; border:1px solid #2a4a7a;
    border-radius:6px; font-family:'IBM Plex Mono',monospace;
    font-size:0.85rem; padding:0.5rem 1.5rem; transition:all 0.2s;
}
.stButton>button:hover { background:#2a4a7a; border-color:#4a6a9a; color:#d0e0f0; }

div[data-testid="stSelectbox"] label,
div[data-testid="stFileUploader"] label,
div[data-testid="stTextInput"] label {
    font-family:'IBM Plex Mono',monospace; font-size:0.8rem;
    color:#7888aa; text-transform:uppercase; letter-spacing:1px;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "temp_dir" not in st.session_state:
    st.session_state.temp_dir = tempfile.mkdtemp(prefix="form_checker_")
    atexit.register(shutil.rmtree, st.session_state.temp_dir, ignore_errors=True)

if "results"        not in st.session_state: st.session_state.results        = {}
if "uploaded_files" not in st.session_state: st.session_state.uploaded_files = {}  # {fname: fpath}
if "type_overrides" not in st.session_state: st.session_state.type_overrides = {}  # {fname: type}
if "input_mode"     not in st.session_state: st.session_state.input_mode     = "folder"

TEMP_DIR = st.session_state.temp_dir
MD_DIR   = os.path.join(TEMP_DIR, "output_of_forms")
os.makedirs(MD_DIR, exist_ok=True)

SUPPORTED_EXTS = {".pdf", ".docx", ".doc"}


# ── Helpers ───────────────────────────────────────────────────────────────────
def detect_form_type(filename: str) -> str:
    name = filename.lower()
    if "3a" in name: return "3a"
    if "3b" in name: return "3b"
    if "3c" in name: return "3c"
    if "3d" in name: return "3d"
    return "unknown"


def scan_directory(dir_path: str) -> dict:
    """Scan directory, return {fname: full_path} for supported files."""
    found = {}
    for f in Path(dir_path).iterdir():
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
            found[f.name] = str(f)
    return found


def register_files(files_dict: dict):
    """Add files to session state without overwriting existing overrides."""
    for fname, fpath in files_dict.items():
        st.session_state.uploaded_files[fname] = fpath
        if fname not in st.session_state.type_overrides:
            st.session_state.type_overrides[fname] = detect_form_type(fname)


def docx_to_markdown(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = para.style.name
        if "Heading 1" in style:   lines.append(f"# {text}")
        elif "Heading 2" in style: lines.append(f"## {text}")
        elif "Heading 3" in style: lines.append(f"### {text}")
        else:                      lines.append(text)
    return "\n".join(lines)


def extract_to_md(file_path: str, form_type: str) -> str:
    import pymupdf4llm
    fp  = Path(file_path)
    ext = fp.suffix.lower()
    out_path = os.path.join(MD_DIR, f"{fp.stem}.md")

    if ext == ".docx":
        md_text = docx_to_markdown(file_path)
    else:
        md_text = pymupdf4llm.to_markdown(file_path)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_text)

    return out_path


def run_checker(form_type: str, file_path: str, md_path: str) -> dict:
    stem    = Path(file_path).stem
    pdf_dir = str(Path(file_path).parent)

    if form_type == "3a":
        from form_checker.for_3a_form import check_3a_form
        return check_3a_form(stem, md_dir=MD_DIR, pdf_dir=pdf_dir)
    elif form_type == "3b":
        from form_checker.for_3b_form import check_3b_form
        return check_3b_form(stem, md_dir=MD_DIR, pdf_dir=pdf_dir)
    elif form_type == "3c":
        from form_checker.for_3c_form import check_3c_form
        return check_3c_form(stem, md_dir=MD_DIR, pdf_dir=pdf_dir)
    elif form_type == "3d":
        from form_checker.for_3d_form import check_form
        return check_form(file_path, md_dir=MD_DIR)
    return {}


def run_all_checks():
    # Sync any selectbox widget values into type_overrides before processing
    for fname in st.session_state.uploaded_files:
        widget_key = f"sel_{fname}"
        if widget_key in st.session_state:
            st.session_state.type_overrides[fname] = st.session_state[widget_key]

    files    = list(st.session_state.uploaded_files.items())
    progress = st.progress(0, text="Starting…")
    errors   = []

    for i, (fname, fpath) in enumerate(files):
        form_type = st.session_state.type_overrides.get(fname, "3d")

        progress.progress(i / len(files), text=f"[{i+1}/{len(files)}] Extracting: {fname}")
        try:
            md_path = extract_to_md(fpath, form_type)
        except Exception as e:
            errors.append(f"Extraction failed — {fname}: {e}")
            continue

        progress.progress((i + 0.5) / len(files), text=f"[{i+1}/{len(files)}] Checking: {fname}")
        try:
            result = run_checker(form_type, fpath, md_path)
            st.session_state.results[fname] = {"form_type": form_type, "data": result}
        except Exception as e:
            errors.append(f"Check failed — {fname}: {e}")

    progress.progress(1.0, text="✔ Done!")

    for err in errors:
        st.error(f"❌ {err}")

    st.success(f"Processed {len(st.session_state.results)} / {len(files)} form(s)")
    st.rerun()


# ── Result card renderer ──────────────────────────────────────────────────────
def render_bool(val) -> str:
    if val is True:  return '<span class="ok">✔ YES</span>'
    if val is False: return '<span class="fail">✘ NO</span>'
    return f'<span class="val">{val}</span>'


def render_result_card(form_name: str, form_type: str, data: dict):
    badge_cls = f"badge-{form_type}"
    st.markdown(
        f'<div class="result-block">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:0.8rem;">'
        f'<span style="font-family:\'IBM Plex Mono\',monospace;font-weight:600;'
        f'font-size:1rem;color:#d0d8f0">{form_name}</span>'
        f'<span class="badge {badge_cls}">{form_type.upper()}</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    if form_type == "3a":
        rows = [
            ("Corresponding Author", data.get("corresponding_author_exists"), data.get("corresponding_author_name")),
            ("Title in Section 1",   data.get("title_in_1_exists"),           data.get("title_in_1_name")),
            ("Title in Section 2",   data.get("title_in_2_exists"),           data.get("title_in_2_name")),
            ("Signature",            data.get("signature_exists"),            None),
            ("Date",                 data.get("date_exists"),                 data.get("date_value")),
            ("Name",                 data.get("name_exists"),                 data.get("name_value")),
            ("Surname",              data.get("surname_exists"),              data.get("surname_value")),
        ]
    elif form_type == "3b":
        rows = [
            ("Paper Title", data.get("paper_title_exists"), data.get("paper_title_name")),
            ("Signature",   data.get("signature_exists"),   None),
            ("Date",        data.get("date_exists"),        data.get("date_value")),
            ("Name",        data.get("name_exists"),        data.get("name_value")),
            ("Surname",     data.get("surname_exists"),     data.get("surname_value")),
        ]
    elif form_type == "3c":
        authors = data.get("signature_of_authors", [])
        rows = [
            ("Paper Title",       data.get("paper_title_exists"),       data.get("paper_title_name")),
            ("Signatures",        data.get("signatures_exist"),         ", ".join(authors) if authors else None),
            ("Co-Author Name",    data.get("co_author_name_exists"),    data.get("name_of_co_author")),
            ("Co-Author Surname", data.get("co_author_surname_exists"), data.get("surname_of_co_author")),
            ("Date",              data.get("date_exists"),              data.get("date")),
        ]
    elif form_type == "3d":
        ref_data = data.get("references", {})
        rows = [
            ("Title Grammar",     data.get("title_grammar"),     data.get("title_name")),
            ("Abstract Suitable", data.get("abstract_suitable"), f"{data.get('abstract_word_count', 0)} words"),
            ("Keywords Suitable", data.get("keywords_suitable"), f"{data.get('keywords_count', 0)} keywords"),
            ("Heading Numbering", data.get("numbering_correct"), None),
            ("All Harvard Refs",  ref_data.get("all_harvard"),   f"{ref_data.get('total_references', 0)} references"),
        ]
    else:
        rows = []

    html_rows = ""
    for label, bool_val, text_val in rows:
        extra = f' &nbsp;<span class="val">— {text_val}</span>' if text_val else ""
        html_rows += (
            f'<div class="check-row">'
            f'<span class="check-label">{label}</span>'
            f'<span>{render_bool(bool_val)}{extra}</span>'
            f'</div>'
        )
    st.markdown(html_rows + "</div>", unsafe_allow_html=True)


def render_unknown_pickers():
    # Only show files whose ORIGINAL filename has no type
    unknown_files = [
        fname for fname in st.session_state.uploaded_files
        if detect_form_type(fname) == "unknown"
    ]
    if not unknown_files:
        return

    st.markdown("""
    <div class="unknown-banner">
        <div class="unknown-banner-title">⚠ Unknown type — select manually</div>
        <div style="font-size:0.78rem;color:#9a9a6a;">
            These files have no form type in their filename. Pick a type and confirm.
        </div>
    </div>
    """, unsafe_allow_html=True)

    selections = {}
    for fname in unknown_files:
        current = st.session_state.type_overrides.get(fname, "3d")
        safe_current = current if current in ["3a", "3b", "3c", "3d"] else "3d"

        c_name, c_sel = st.columns([2.2, 1])
        with c_name:
            st.markdown(
                f'<div style="padding:5px 0;font-size:0.82rem;color:#cfcf4f;">' +
                f'? {fname[:36]}{"..." if len(fname) > 36 else ""}</div>',
                unsafe_allow_html=True
            )
        with c_sel:
            sel = st.selectbox(
                "type", ["3a", "3b", "3c", "3d"],
                index=["3a", "3b", "3c", "3d"].index(safe_current),
                key=f"sel_{fname}",
                label_visibility="collapsed"
            )
        selections[fname] = sel

    # Confirm button — explicitly commits all selections to type_overrides
    if st.button("✅  Confirm Type Selections", use_container_width=True):
        for fname, sel in selections.items():
            st.session_state.type_overrides[fname] = sel
        st.success("Types saved!")
        st.rerun()
    else:
        # Also keep updating on every render so Run All Checks always sees latest value
        for fname, sel in selections.items():
            st.session_state.type_overrides[fname] = sel

    st.markdown("---")


def render_file_list():
    if not st.session_state.uploaded_files:
        return
    st.markdown("**Files queued**")
    for fname in st.session_state.uploaded_files:
        form_type  = st.session_state.type_overrides.get(fname, "unknown")
        badge_cls  = f"badge-{form_type}" if form_type != "unknown" else "badge-unknown"
        done_icon  = "✔" if fname in st.session_state.results else "○"
        done_color = "#4caf84" if fname in st.session_state.results else "#4a5a7a"
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'padding:5px 0;border-bottom:1px solid #1a1a2a;">'
            f'<span style="font-size:0.8rem;color:#b0b8c8">'
            f'{fname[:34]}{"…" if len(fname) > 34 else ""}</span>'
            f'<span style="display:flex;align-items:center;gap:8px;">'
            f'<span class="badge {badge_cls}">{form_type.upper()}</span>'
            f'<span style="color:{done_color};font-size:0.85rem">{done_icon}</span>'
            f'</span></div>',
            unsafe_allow_html=True
        )


def render_action_buttons():
    st.markdown("---")
    run_col, clear_col = st.columns(2)
    with run_col:
        run_btn = st.button("▶  Run All Checks", use_container_width=True)
    with clear_col:
        if st.button("🗑  Clear All", use_container_width=True):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            os.makedirs(TEMP_DIR, exist_ok=True)
            os.makedirs(MD_DIR, exist_ok=True)
            st.session_state.uploaded_files = {}
            st.session_state.type_overrides = {}
            st.session_state.results        = {}
            st.rerun()
    if run_btn:
        run_all_checks()


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
    <div class="app-title">📋 Form Checker</div>
    <div class="app-subtitle">Folder scan or file upload · Auto-detect type · Run checks · Export to Excel</div>
</div>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([1, 1.6], gap="large")

# ══════════════════════════════════════════════════════════════════════════════
# LEFT COLUMN — Input
# ══════════════════════════════════════════════════════════════════════════════
with col_left:
    st.markdown("### Input")

    # ── Mode toggle ───────────────────────────────────────────────────────────
    mode_col1, mode_col2 = st.columns(2)
    with mode_col1:
        if st.button("📁  Folder", use_container_width=True):
            st.session_state.input_mode = "folder"
    with mode_col2:
        if st.button("📄  Upload Files", use_container_width=True):
            st.session_state.input_mode = "upload"

    mode = st.session_state.input_mode
    st.markdown(
        f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:0.75rem;'
        f'color:#4a6a9a;margin-bottom:1rem;">Mode: <b style="color:#7a9aca">{mode.upper()}</b></div>',
        unsafe_allow_html=True
    )

    # ══════════════════════════════════════════════════════════════════════════
    # FOLDER MODE
    # ══════════════════════════════════════════════════════════════════════════
    if mode == "folder":
        dir_path = st.text_input(
            "Directory path",
            placeholder="/path/to/your/forms",
            key="dir_input"
        )

        if dir_path:
            if not os.path.isdir(dir_path):
                st.error("❌ Directory not found. Please check the path.")
            else:
                found = scan_directory(dir_path)
                if not found:
                    st.warning("⚠ No PDF or DOCX files found in this directory.")
                else:
                    # Categorize preview
                    cats = {"3a": [], "3b": [], "3c": [], "3d": [], "unknown": []}
                    for fname in found:
                        cats[detect_form_type(fname)].append(fname)

                    st.markdown(f"""
                    <div class="dir-box">
                        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.85rem;
                                    color:#b0c8e8;font-weight:600;">📁 {dir_path}</div>
                        <div class="dir-stat">
                            {len(found)} file(s) found &nbsp;·&nbsp;
                            <span style="color:#4caf84">{len(cats['3a'])} × 3A</span> &nbsp;·&nbsp;
                            <span style="color:#4a8fcf">{len(cats['3b'])} × 3B</span> &nbsp;·&nbsp;
                            <span style="color:#9a6fcf">{len(cats['3c'])} × 3C</span> &nbsp;·&nbsp;
                            <span style="color:#cf9a4f">{len(cats['3d'])} × 3D</span> &nbsp;·&nbsp;
                            <span style="color:#cfcf4f">{len(cats['unknown'])} unknown</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button("📥  Load All Files from Folder", use_container_width=True):
                        register_files(found)
                        st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # UPLOAD MODE
    # ══════════════════════════════════════════════════════════════════════════
    else:
        uploaded = st.file_uploader(
            "Drop PDF or DOCX files",
            type=["pdf", "docx", "doc"],
            accept_multiple_files=True,
            key="uploader"
        )

        if uploaded:
            newly_added = 0
            for uf in uploaded:
                if uf.name not in st.session_state.uploaded_files:
                    save_path = os.path.join(TEMP_DIR, uf.name)
                    with open(save_path, "wb") as f:
                        f.write(uf.read())
                    st.session_state.uploaded_files[uf.name] = save_path
                    if uf.name not in st.session_state.type_overrides:
                        st.session_state.type_overrides[uf.name] = detect_form_type(uf.name)
                    newly_added += 1
            if newly_added:
                st.rerun()

    # ── Unknown pickers (shared for both modes) ───────────────────────────────
    if st.session_state.uploaded_files:
        st.markdown("---")
        render_unknown_pickers()
        render_file_list()
        render_action_buttons()

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT COLUMN — Results & Export
# ══════════════════════════════════════════════════════════════════════════════
with col_right:
    st.markdown("### Results")

    if not st.session_state.results:
        st.markdown(
            '<div style="color:#4a5a7a;font-size:0.9rem;padding:2rem 0;">'
            'Load files and click <b>▶ Run All Checks</b> to see results here.</div>',
            unsafe_allow_html=True
        )
    else:
        counts = {"3a": 0, "3b": 0, "3c": 0, "3d": 0}
        for v in st.session_state.results.values():
            ft = v.get("form_type", "3d")
            counts[ft] += 1

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total", len(st.session_state.results))
        m2.metric("3A",    counts["3a"])
        m3.metric("3B",    counts["3b"])
        m4.metric("3C",    counts["3c"])
        m5.metric("3D",    counts["3d"])

        st.markdown("---")

        for fname, entry in st.session_state.results.items():
            render_result_card(
                form_name=Path(fname).stem,
                form_type=entry["form_type"],
                data=entry["data"]
            )

        st.markdown("---")
        st.markdown("### Export")

        from utils.excel_writer import build_excel
        excel_bytes = build_excel(st.session_state.results)

        st.download_button(
            label="⬇  Download Excel Report",
            data=excel_bytes,
            file_name="form_checker_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        with st.expander("🔍 View raw JSON"):
            st.json(st.session_state.results)