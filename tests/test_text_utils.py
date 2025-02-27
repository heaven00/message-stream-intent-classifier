from text_utils import clean_text


def test_remove_urls():
    assert clean_text("Check out http://example.com ") == "check out link"


def test_remove_mentions():
    assert clean_text("hi @t_we ") == "hi user"
    assert clean_text("hey #channel") == "hey group"


def test_remove_special_chars():
    assert clean_text("Hell*, w(&ld!.") == "hell, wld!."
