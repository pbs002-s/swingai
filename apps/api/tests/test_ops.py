"""Operability: request IDs and Bangla error messages."""

import logging

from app.core.request_id import RequestIdFilter, new_request_id, request_id_var


async def test_every_response_carries_a_request_id_and_keeps_a_safe_client_one(anon):
    r = await anon.get("/healthz")
    assert len(r.headers["x-request-id"]) == 32

    mine = "client-trace-12345"
    assert (await anon.get("/healthz", headers={"x-request-id": mine})).headers["x-request-id"] == mine
    forged = (await anon.get("/healthz", headers={"x-request-id": "a b\r\nINFO fake log line"})).headers["x-request-id"]
    assert forged != "a b" and len(forged) == 32  # anything that could forge a log line is replaced


def test_log_lines_carry_the_request_id():
    token = request_id_var.set("abc12345")
    try:
        record = logging.LogRecord("x", logging.INFO, "f", 1, "msg", None, None)
        assert RequestIdFilter().filter(record) and record.request_id == "abc12345"
    finally:
        request_id_var.reset(token)
    assert new_request_id(None) != new_request_id(None)


async def test_errors_speak_bangla_only_when_asked(anon):
    en = (await anon.get("/auth/me")).json()["error"]
    bn = (await anon.get("/auth/me", headers={"accept-language": "bn-BD,bn;q=0.9,en;q=0.8"})).json()["error"]
    assert en["code"] == bn["code"] == "UNAUTHENTICATED"  # the code never changes
    assert en["message"] == "Log in to continue." and "লগ ইন" in bn["message"]

    unknown = (await anon.get("/nope", headers={"accept-language": "bn"})).json()["error"]
    assert unknown["code"] == "NOT_FOUND" and "খুঁজে" in unknown["message"]
    fr = (await anon.get("/auth/me", headers={"accept-language": "fr"})).json()["error"]
    assert fr["message"] == en["message"]  # other languages fall back to English
