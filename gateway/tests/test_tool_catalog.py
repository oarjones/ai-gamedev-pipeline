from app.services.tool_catalog import build_catalog, get_catalog_cached


def test_build_catalog_minimum():
    cat = build_catalog()
    assert isinstance(cat, dict)
    assert isinstance(cat.get("hash"), str) and len(cat["hash"]) >= 8
    assert isinstance(cat.get("promptList"), str)
    assert isinstance(cat.get("functionSchema"), list)
    assert cat.get("count", 0) > 0


def test_get_catalog_cached_roundtrip(tmp_path, monkeypatch):
    cat1 = build_catalog()
    cat2 = get_catalog_cached()
    assert cat2.get("hash") == cat1.get("hash")
    assert cat2.get("count") == cat1.get("count")

