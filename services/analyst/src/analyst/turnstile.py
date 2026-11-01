"""The Cloudflare Turnstile check: the page gets a token, and the API asks Cloudflare about it."""

import logging
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# The check comes before each paid question, and the visitor waits for it. httpx
# gives each phase of a call its own limit, so the two limits add up: the call
# ends within about 5 s. The body that goes out is small, so writing it is fast.
CONNECT_SECONDS = 2.0
READ_SECONDS = 3.0

# "unavailable" is a Cloudflare that gave no clear answer, not a bad token.
Verdict = Literal["passed", "failed", "unavailable"]


def make_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(READ_SECONDS, connect=CONNECT_SECONDS))


def verify(client: httpx.Client, secret: str, token: str, address: str) -> Verdict:
    """Ask Cloudflare whether the token is valid for this address.

    The log lines hold the error codes or the class of the error, never the token
    or the secret.
    """
    try:
        response = client.post(
            SITEVERIFY_URL, data={"secret": secret, "response": token, "remoteip": address}
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("turnstile unavailable: %s", type(error).__name__)
        return "unavailable"
    success = body.get("success") if isinstance(body, dict) else None
    if not isinstance(success, bool):
        logger.warning("turnstile unavailable: the answer has no success flag")
        return "unavailable"
    if success:
        return "passed"
    codes = body.get("error-codes")
    # The codes are short names from Cloudflare, such as "timeout-or-duplicate".
    shown = [code for code in codes if isinstance(code, str)] if isinstance(codes, list) else []
    logger.warning("turnstile failed: %s", ", ".join(shown) or "no code")
    return "failed"
