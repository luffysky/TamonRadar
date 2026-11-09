import json
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

import db
import notify
import watcher


def soup(html):
    return BeautifulSoup(html, "lxml")


def detect(html, avail=None, unavail=None):
    return watcher.detect_availability(soup(html), avail or [], unavail or [])


def ld(data):
    return f'<script type="application/ld+json">{json.dumps(data)}</script>'


def product(availability):
    return {"@context": "https://schema.org", "@type": "Product", "name": "X",
            "offers": {"@type": "Offer", "price": "100", "availability": availability}}


# ---------- 關鍵字 / 整字比對 ----------

def test_unavailable_does_not_match_available():
    assert watcher._evaluate("this item is unavailable", ["available"], []) == "unavailable"


def test_available_word_needs_boundaries():
    assert watcher._evaluate("this item is unavailable", ["available"], ["nothing-matches"]) == "unknown"
    assert watcher._evaluate("now available here", ["available"], ["nothing-matches"]) == "available"


def test_unavailable_keyword_wins_over_available():
    assert watcher._evaluate("Sold out. Add to cart", [], []) == "unavailable"


def test_chinese_keywords_substring():
    assert watcher._evaluate("本商品已售完,敬請見諒", [], []) == "unavailable"
    assert watcher._evaluate("立即購買享優惠", [], []) == "available"


def test_english_phrase_matches_flexible_whitespace():
    assert watcher._evaluate("add   to\ncart", [], []) == "available"


def test_custom_keywords_override_defaults():
    assert watcher._evaluate("開放搶購中", ["搶購"], ["關閉"]) == "available"
    assert watcher._evaluate("Sold out", ["搶購"], ["關閉"]) == "unknown"


# ---------- 結構化資料 ----------

def test_jsonld_out_of_stock_beats_visible_buy_button():
    assert detect(ld(product("https://schema.org/OutOfStock")) + "<body>Add to cart</body>") == "unavailable"


def test_jsonld_in_stock_beats_visible_sold_out_text():
    assert detect(ld(product("http://schema.org/InStock")) + "<body>Other item sold out</body>") == "available"


def test_jsonld_preorder_counts_available():
    assert detect(ld(product("PreOrder"))) == "available"


def test_jsonld_any_variant_available():
    data = {"@type": "Product", "offers": [
        {"@type": "Offer", "availability": "https://schema.org/SoldOut"},
        {"@type": "Offer", "availability": "https://schema.org/InStock"},
    ]}
    assert detect(ld(data)) == "available"


def test_jsonld_graph_supported():
    assert detect(ld({"@graph": [{"@type": "WebPage"}, product("OutOfStock")]})) == "unavailable"


def test_jsonld_related_product_ignored():
    data = product("OutOfStock")
    data["isRelatedTo"] = product("InStock")
    assert detect(ld(data)) == "unavailable"


def test_jsonld_mixed_products_fall_through_to_text():
    html = ld([product("InStock"), product("OutOfStock")]) + "<body>Sold out</body>"
    assert detect(html) == "unavailable"
    html2 = ld([product("InStock"), product("OutOfStock")]) + "<body>nothing relevant</body>"
    assert detect(html2) == "unknown"


def test_broken_jsonld_ignored():
    assert detect('<script type="application/ld+json">{broken</script><body>售完</body>') == "unavailable"


def test_microdata_availability():
    html = '<div itemscope><link itemprop="availability" href="https://schema.org/SoldOut"/></div><body>Buy now</body>'
    assert detect(html) == "unavailable"


def test_meta_product_availability():
    assert detect('<head><meta property="product:availability" content="oos"></head><body>Buy now</body>') == "unavailable"


# ---------- 內嵌 JSON ----------

def test_json_available_false():
    assert detect('<script>var p = {"title":"X","available":false};</script><body>Add to cart</body>') == "unavailable"


def test_json_available_true():
    assert detect('<script>var p = {"available":true};</script><body>nothing</body>') == "available"


def test_json_escaped_in_stock_false():
    assert detect('<script>self.__next_f.push("{\\"inStock\\":false}")</script><body>x</body>') == "unavailable"


def test_json_sold_out_true():
    assert detect('<script>{"sold_out":true}</script>') == "unavailable"


def test_json_availability_string():
    assert detect('<script>{"availability":"OutOfStock"}</script>') == "unavailable"


def test_json_mixed_signals_fall_through_to_text():
    html = '<script>{"available":true,"variants":[{"available":false}]}</script><body>Add to cart</body>'
    assert detect(html) == "available"


# ---------- 只看可見文字 ----------

def test_raw_html_not_scanned():
    assert detect('<body data-x="sold out"><!-- sold out --><script>var msg="sold out";</script>Buy now</body>') == "available"


def test_hidden_elements_ignored():
    html = '<body><span style="display: none">Sold out</span><span hidden>售完</span>Add to cart</body>'
    assert detect(html) == "available"


def test_unknown_when_no_signal():
    assert detect("<body>hello world</body>") == "unknown"


# ---------- check_watch:錯誤狀態與補貨通知 ----------

def page_response(status=200, text="<html><body>hello</body></html>"):
    return SimpleNamespace(status_code=status, text=text, headers={})


@pytest.fixture
def watch(make_user):
    user = make_user()
    w = db.create_watch(user.id, {"url": "https://shop.example.com/item", "name": "商品", "interval_minutes": 10})
    return w


@pytest.fixture
def sent(monkeypatch):
    messages = []
    monkeypatch.setattr(notify, "notify_all", lambda settings, text, embed=None: messages.append(text) or {})
    return messages


def set_response(monkeypatch, resp):
    monkeypatch.setattr(watcher, "safe_get", lambda *a, **k: resp)


def set_status(w, status):
    db.set_watch_status(w["id"], status)


@pytest.mark.parametrize("code", [403, 404, 500, 503])
def test_http_error_is_error_state_not_status_change(monkeypatch, watch, sent, code):
    set_status(watch, "unavailable")
    # 503 頁面裡即使有購買字眼也不能當成可買
    set_response(monkeypatch, page_response(code, "<body>Buy now Add to cart</body>"))
    res = watcher.check_watch(watch["id"])
    assert res["ok"] is False and res["status"] == "error"
    after = db.get_watch(watch["id"])
    assert after["last_status"] == "unavailable"
    assert str(code) in after["last_error"]
    assert after["last_checked"] is not None
    assert sent == []


def test_cloudflare_challenge_is_error(monkeypatch, watch, sent):
    set_status(watch, "unavailable")
    set_response(monkeypatch, page_response(200, "<title>Just a moment...</title><body>Checking your browser</body>"))
    res = watcher.check_watch(watch["id"])
    assert res["status"] == "error"
    assert db.get_watch(watch["id"])["last_status"] == "unavailable"
    assert sent == []


def test_network_exception_is_error(monkeypatch, watch, sent):
    def boom(*a, **k):
        raise ConnectionError("network down")

    monkeypatch.setattr(watcher, "safe_get", boom)
    res = watcher.check_watch(watch["id"])
    assert res["status"] == "error"
    assert "network down" in db.get_watch(watch["id"])["last_error"]
    assert sent == []


def test_restock_fires_from_unavailable(monkeypatch, watch, sent):
    set_status(watch, "unavailable")
    set_response(monkeypatch, page_response(200, "<body>Add to cart</body>"))
    res = watcher.check_watch(watch["id"])
    assert res["status"] == "available" and res["notified"] is True
    assert len(sent) == 1
    after = db.get_watch(watch["id"])
    assert after["last_status"] == "available" and after["last_error"] == ""


@pytest.mark.parametrize("prev", ["unknown", "available", "watching"])
def test_restock_not_fired_from_other_states(monkeypatch, watch, sent, prev):
    set_status(watch, prev)
    set_response(monkeypatch, page_response(200, "<body>Add to cart</body>"))
    watcher.check_watch(watch["id"])
    assert sent == []


def test_restock_after_transient_error_still_fires(monkeypatch, watch, sent):
    set_status(watch, "unavailable")
    set_response(monkeypatch, page_response(503))
    watcher.check_watch(watch["id"])
    assert sent == []
    set_response(monkeypatch, page_response(200, "<body>Add to cart</body>"))
    watcher.check_watch(watch["id"])
    assert len(sent) == 1
    assert db.get_watch(watch["id"])["last_error"] == ""


def test_unavailable_page_does_not_fire_or_mark_available(monkeypatch, watch, sent):
    set_status(watch, "unavailable")
    set_response(monkeypatch, page_response(200, '<script>{"available":false}</script><body>unavailable</body>'))
    res = watcher.check_watch(watch["id"])
    assert res["status"] == "unavailable"
    assert sent == []


def test_watch_list_exposes_last_error(client, make_user, bearer):
    user = make_user()
    w = db.create_watch(user.id, {"url": "https://shop.example.com/a"})
    db.set_watch_error(w["id"], "網站回應 HTTP 503")
    data = client.get("/api/watches", headers=bearer(user)).json()["watches"][0]
    assert data["last_error"] == "網站回應 HTTP 503"
    assert data["last_checked"]
