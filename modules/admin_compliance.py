# modules/admin_compliance.py
from pathlib import Path
import sys, subprocess, datetime
import streamlit as st

def _root_dir() -> Path:
    # このファイルの「1つ上」がプロジェクト直下（ai-writer-mvp）
    return Path(__file__).resolve().parents[1]

def _paths():
    ROOT = _root_dir()
    COMP = ROOT / "compliance"
    return {
        "ROOT": ROOT,
        "REPORTS": COMP / "reports",
        "SCRIPTS": COMP / "scripts",
        "SEMI": (COMP / "scripts" / "compliance_review.py"),
        "MONTH": (COMP / "scripts" / "mini_audit.py"),
        "WEEK": (COMP / "scripts" / "support_sla_weekly.py"),
    }

def _run_script(pyfile: Path):
    # 今動いているPython（Streamlit）でそのまま実行します
    try:
        out = subprocess.run([sys.executable, str(pyfile)], capture_output=True, text=True, timeout=300)
        ok = (out.returncode == 0)
        return ok, (out.stdout or "") + "\n" + (out.stderr or "")
    except Exception as e:
        return False, f"ERROR: {e}"

def _list_reports(report_dir: Path, limit: int = 20):
    if not report_dir.exists():
        return []
    files = [p for p in report_dir.glob("*.md")]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]

def render():
    P = _paths()

    st.title("Admin → Compliance（監査レポート）")

    # ① 今すぐ実行ボタン
    col1, col2, col3 = st.columns(3)
    if col1.button("半期レビューを今すぐ実行", use_container_width=True):
        ok, log = _run_script(P["SEMI"])
        st.success("完了しました。") if ok else st.error("エラーが起きました。")
        with st.expander("実行ログを開く"):
            st.code(log)

    if col2.button("月次ミニ監査を今すぐ実行", use_container_width=True):
        ok, log = _run_script(P["MONTH"])
        st.success("完了しました。") if ok else st.error("エラーが起きました。")
        with st.expander("実行ログを開く"):
            st.code(log)

    if col3.button("週間SLAを今すぐ実行", use_container_width=True):
        ok, log = _run_script(P["WEEK"])
        st.success("完了しました。") if ok else st.error("エラーが起きました。")
        with st.expander("実行ログを開く"):
            st.code(log)

    st.divider()

    # ② レポート一覧（新しい順）
    st.subheader("最新レポート一覧")
    files = _list_reports(P["REPORTS"], limit=50)
    if not files:
        st.info("まだレポートがありません。上のボタンで作成できます。")
        return

    # 左：選ぶ / 右：内容表示
    left, right = st.columns([1,2])
    labels = [f"{f.name}（{datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')}）" for f in files]
    idx = left.selectbox("レポートを選ぶ", options=list(range(len(files))), format_func=lambda i: labels[i])

    sel = files[idx]
    with sel.open(encoding="utf-8", errors="ignore") as r:
        content = r.read()

    right.download_button("↓ このレポートをダウンロード", data=content, file_name=sel.name, mime="text/markdown", use_container_width=True)
    right.markdown(content)
