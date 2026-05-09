import csv
from datetime import datetime
from pathlib import Path

def append_log(keyword, filename, result="成功", note=""):
    log_path = Path(__file__).parent / "manuals" / "progress_log.csv"
    log_path.parent.mkdir(exist_ok=True)
    exists = log_path.exists()
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["日付", "キーワード", "出力ファイル名", "結果", "備考"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            keyword,
            filename,
            result,
            note
        ])
