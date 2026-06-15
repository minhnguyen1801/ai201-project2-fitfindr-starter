import pytest
from unittest.mock import patch
from types import SimpleNamespace

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe, load_listings


# Use a real sample listing from the bundled dataset for tests that need an item
LISTINGS = load_listings()
some_item = LISTINGS[0]


def test_search_returns_results():
    res = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(res, list)
    assert len(res) > 0


def test_search_empty_results():
    res = search_listings("designer ballgown", size="XXS", max_price=5)
    assert res == []


def test_search_price_filter():
    res = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in res)


def test_search_size_filter():
    res = search_listings("tee", size="XL", max_price=None)
    assert all("xl" in item["size"].lower() for item in res)


# --- Helpers to mock the Groq/LLM client ---
class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, message):
        self.message = message


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(FakeMessage(content))]


def make_fake_client(response_text="mocked response"):
    def create(*args, **kwargs):
        return FakeResponse(response_text)

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_suggest_outfit_empty_wardrobe():
    with patch("tools._get_groq_client", return_value=make_fake_client("General styling ideas")):
        res = suggest_outfit(some_item, get_empty_wardrobe())
    assert isinstance(res, str)
    assert res.strip()


def test_suggest_outfit_with_wardrobe():
    with patch("tools._get_groq_client", return_value=make_fake_client("Specific outfit combos")):
        res = suggest_outfit(some_item, get_example_wardrobe())
    assert isinstance(res, str)
    assert res.strip()


def test_fit_card_empty_outfit():
    res = create_fit_card("", some_item)
    assert res == "Cannot generate a fit card without an outfit suggestion."


def test_fit_card_whitespace_outfit():
    res = create_fit_card(" ", some_item)
    assert res == "Cannot generate a fit card without an outfit suggestion."
