import logging

import httpx
import pytest

from analyst import turnstile

SECRET = "the-secret"
TOKEN = "the-token"


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def replies(status: int, body) -> httpx.Client:
    """A client whose siteverify call gets this status and JSON body."""
    return client_for(lambda request: httpx.Response(status, json=body))


def test_the_call_sends_the_secret_the_token_and_the_address():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"success": True})

    turnstile.verify(client_for(handler), SECRET, TOKEN, "203.0.113.7")

    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == turnstile.SITEVERIFY_URL
    assert dict(httpx.QueryParams(request.content.decode())) == {
        "secret": SECRET,
        "response": TOKEN,
        "remoteip": "203.0.113.7",
    }


def test_a_token_that_cloudflare_accepts_passes():
    assert turnstile.verify(replies(200, {"success": True}), SECRET, TOKEN, "a") == "passed"


def test_a_token_that_cloudflare_refuses_fails_and_the_log_has_only_the_codes(caplog):
    body = {"success": False, "error-codes": ["invalid-input-response"]}

    with caplog.at_level(logging.WARNING, logger="analyst.turnstile"):
        verdict = turnstile.verify(replies(200, body), SECRET, TOKEN, "a")

    assert verdict == "failed"
    assert "invalid-input-response" in caplog.text
    assert TOKEN not in caplog.text
    assert SECRET not in caplog.text


def timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("slow", request=request)


def refused(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("down", request=request)


@pytest.mark.parametrize(
    "client",
    [
        client_for(timeout),
        client_for(refused),
        replies(500, {"success": False}),
        replies(200, ["not", "an", "object"]),
        replies(200, {"success": "yes"}),
        client_for(lambda request: httpx.Response(200, content=b"<html>")),
    ],
    ids=["timeout", "no-connection", "5xx", "not-an-object", "no-boolean", "not-json"],
)
def test_cloudflare_that_does_not_answer_clearly_is_unavailable(client, caplog):
    with caplog.at_level(logging.WARNING, logger="analyst.turnstile"):
        verdict = turnstile.verify(client, SECRET, TOKEN, "a")

    assert verdict == "unavailable"
    assert TOKEN not in caplog.text
    assert SECRET not in caplog.text


def test_the_connect_and_the_read_together_stay_within_5_seconds():
    timeout = turnstile.make_client().timeout

    assert timeout.connect is not None and timeout.read is not None
    assert timeout.connect + timeout.read <= 5.0
