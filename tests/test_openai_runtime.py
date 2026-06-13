import openai_runtime


def test_generate_markdown_demo_does_not_call_openai(monkeypatch):
    class FailingOpenAI:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("OpenAI should not be used for demo generation")

    monkeypatch.setattr(openai_runtime, "OpenAI", FailingOpenAI)

    result = openai_runtime.generate_markdown(
        prompt="お客さま向けの紹介文です。",
        model="gpt-4o-mini",
        use_real_api=False,
        openai_api_key="",
        timeout_sec=10,
    )

    assert "サンプル表示" in result
    assert "プロンプト（デモ）" not in result
    assert "最重要ルール" not in result
    assert "あなたは日本語でSEO記事" not in result
