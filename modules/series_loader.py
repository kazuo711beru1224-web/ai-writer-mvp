# modules/series_loader.py
from pathlib import Path

# プロジェクトのルートディレクトリを推定
BASE_DIR = Path(__file__).resolve().parent.parent

def load_series_yaml(series_id: str) -> str:
    """
    シリーズIDからYAMLファイルを読み込み、文字列として返す。
    GPTプロンプトにそのまま埋め込む用途。
    """
    series_path = BASE_DIR / "briefs" / "series" / f"{series_id}.yaml"
    if not series_path.exists():
        raise FileNotFoundError(f"シリーズYAMLが見つかりません: {series_path}")

    text = series_path.read_text(encoding="utf-8")
    return text
