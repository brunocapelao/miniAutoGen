from miniautogen.app.notebook_cache import ResponseCache


def test_response_cache_roundtrip(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache.json")
    key = "lead-plan"
    cache.set(key, {"text": "ok"})

    assert cache.get(key) == {"text": "ok"}
