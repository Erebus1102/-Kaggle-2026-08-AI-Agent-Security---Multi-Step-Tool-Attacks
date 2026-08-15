from attack import post_msg, deputy_msg, SECRET_MARKER, MAX_MESSAGE_CHARS

_URL = "https://report.example.org/log"
_RECIPIENT = "bob@example.org"


def test_post_msg_shape():
    msg = post_msg(_URL)
    assert _URL in msg and SECRET_MARKER in msg
    assert msg.endswith("Then answer OK only.")
    assert len(msg) <= MAX_MESSAGE_CHARS


def test_deputy_msg_avoids_authorization_keywords():
    # CONFUSED_DEPUTY only fires when the LAST user message lacks these.
    msg = deputy_msg(_RECIPIENT)
    lower = msg.lower()
    for banned in ("send", "email", "upload"):
        assert banned not in lower
    assert _RECIPIENT in msg
    assert len(msg) <= MAX_MESSAGE_CHARS
