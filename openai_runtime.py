from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI


class OpenAIRuntimeError(RuntimeError):
    """OpenAI呼び出し周りの実行時エラーをまとめるためのアプリ内例外。"""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "unknown_error",
        user_message: str = "",
        detail: str = "",
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.user_message = user_message or message
        self.detail = detail or message


def _classify_openai_error_message(message: str) -> tuple[str, str]:
    msg = (message or "").lower()

    if "api key" in msg and ("incorrect" in msg or "invalid" in msg or "malformed" in msg):
        return (
            "auth_error",
            "APIキーが正しくない可能性があります。保存してあるAPIキーを見直してください。",
        )

    if "authentication" in msg or "unauthorized" in msg or "invalid_api_key" in msg:
        return (
            "auth_error",
            "APIキーの確認が必要です。保存してあるAPIキーを見直してください。",
        )

    if "quota" in msg or "billing" in msg or "insufficient_quota" in msg:
        return (
            "rate_limit_or_quota",
            "OpenAIの残高や請求設定を確認してください。",
        )

    if "rate limit" in msg or "too many requests" in msg:
        return (
            "rate_limit_or_quota",
            "OpenAIへのアクセスが集中しています。少し時間をおいてもう一度お試しください。",
        )

    if "model" in msg and (
        "not found" in msg
        or "does not exist" in msg
        or "unsupported" in msg
        or "unavailable" in msg
    ):
        return (
            "model_error",
            "AIの種類の設定が合っていない可能性があります。アプリの設定を確認してください。",
        )

    if "timeout" in msg or "timed out" in msg:
        return (
            "timeout",
            "OpenAIからの返答に時間がかかっています。時間をおいてもう一度お試しください。",
        )

    if (
        "connection" in msg
        or "connect" in msg
        or "network" in msg
        or "dns" in msg
        or "ssl" in msg
        or "socket" in msg
    ):
        return (
            "connection_error",
            "OpenAIにつながっていません。時間をおいてもう一度お試しください。",
        )

    return (
        "unknown_error",
        "AI下書きを始められませんでした。時間をおいてもう一度お試しください。",
    )


def generate_markdown(
    *,
    prompt: str,
    model: Optional[str],
    use_real_api: bool,
    openai_api_key: str,
    timeout_sec: int,
) -> str:
    """
    単一契約:
      - 生成はこの関数だけ
      - APIキーは環境変数に一時注入し、SDKへ直接渡す方式は使わない
    """
    prompt = (prompt or "").strip()

    if not use_real_api:
        head = "# デモ下書き（API未使用）\n\n"
        body = """これは、APIキーを入力していないときに表示されるサンプルです。
本番AIは使っていません。

例：
雨の日でも立ち寄りやすいように、温かい飲み物とすぐ食べられる商品を入口近くで案内します。
短いPOPでは、「帰り道に、ほっと一息。」のように、お客様の気持ちに合わせた一言を使います。

APIキーを入力すると、入力内容に合わせた下書きをAIで作成できます。
"""
        return head + body

    if not openai_api_key or not openai_api_key.strip():
        raise OpenAIRuntimeError(
            "OpenAI APIキーが空です（本生成ONなのにキーがありません）。",
            error_code="api_key_missing",
            user_message="OpenAI APIキーが入っていません。保存してあるAPIキーを貼り付けてください。",
            detail="OpenAI APIキーが空です（本生成ONなのにキーがありません）。",
        )

    timeout = int(timeout_sec) if isinstance(timeout_sec, int) else 60
    if timeout <= 0:
        timeout = 60

    prev = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = openai_api_key.strip()

    try:
        client = OpenAI(timeout=timeout)
        _model = model.strip() if (model and model.strip()) else "gpt-4o-mini"

        resp = client.chat.completions.create(
            model=_model,
            messages=[
                {"role": "system", "content": "あなたは優秀な日本語ライターです。"},
                {"role": "user", "content": prompt},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    except OpenAIRuntimeError:
        raise

    except Exception as e:
        raw = str(e)
        error_code, user_message = _classify_openai_error_message(raw)
        raise OpenAIRuntimeError(
            raw,
            error_code=error_code,
            user_message=user_message,
            detail=raw,
        ) from e

    finally:
        if prev is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = prev