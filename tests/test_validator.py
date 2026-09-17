import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.downloader import extract_pinterest_url, is_pinterest_url



def test_pinterest_pin_url():
    assert is_pinterest_url("https://www.pinterest.com/pin/123456789/")


def test_pinterest_country_subdomain():
    assert is_pinterest_url("https://in.pinterest.com/pin/987654321/")
    assert is_pinterest_url("https://pinterest.co.uk/pin/1122334455/")


def test_pin_it_url():
    assert is_pinterest_url("https://pin.it/AbCd123")


def test_extract_from_user_text():
    text = "Hey check this video: https://pin.it/AbCd123 from pinterest!"
    extracted = extract_pinterest_url(text)
    assert extracted == "https://pin.it/AbCd123"


def test_rejects_other_url():
    assert not is_pinterest_url("https://example.com/video")
    assert not is_pinterest_url("https://youtube.com/watch?v=12345")
    assert not is_pinterest_url("Just random text without link")
    assert not is_pinterest_url("")

