#!/usr/bin/env python3
"""Production smoke tests for Vanadium deployments.

Usage:
  python scripts/smoke_test.py
  API_URL=https://vanadium-api.onrender.com FRONTEND_ORIGIN=https://app.vercel.app python scripts/smoke_test.py
  API_URL=... TEST_YT_URL_A=... TEST_YT_URL_B=... python scripts/smoke_test.py  # full ingest test
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "").strip()
TEST_YT_URL_A = os.environ.get("TEST_YT_URL_A", "").strip()
TEST_YT_URL_B = os.environ.get("TEST_YT_URL_B", "").strip()


def _request(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict | str]:
    url = f"{API_URL}{path}"
    data = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def test_health() -> None:
    print("-> GET /api/health")
    status, payload = _request("GET", "/api/health")
    if status != 200:
        raise AssertionError(f"health failed: HTTP {status} — {payload}")
    if not isinstance(payload, dict) or "version" not in payload:
        raise AssertionError(f"unexpected health payload: {payload}")
    print(f"  OK version={payload.get('version')} llm={payload.get('llm_configured')}")


def test_cors() -> None:
    if not FRONTEND_ORIGIN:
        print("-> CORS (skipped — set FRONTEND_ORIGIN to test)")
        return
    print(f"-> CORS preflight from {FRONTEND_ORIGIN}")
    url = f"{API_URL}/api/health"
    req = urllib.request.Request(
        url,
        method="OPTIONS",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        allow_origin = resp.headers.get("Access-Control-Allow-Origin", "")
        if allow_origin not in (FRONTEND_ORIGIN, "*"):
            raise AssertionError(
                f"CORS blocked: Access-Control-Allow-Origin={allow_origin!r}"
            )
    print("  OK")


def test_ingest_youtube() -> None:
    if not TEST_YT_URL_A or not TEST_YT_URL_B:
        print("-> POST /api/ingest (skipped — set TEST_YT_URL_A and TEST_YT_URL_B)")
        return
    print("-> POST /api/ingest (YouTube pair — may take 1-3 min)")
    status, payload = _request(
        "POST",
        "/api/ingest",
        {"video_a_url": TEST_YT_URL_A, "video_b_url": TEST_YT_URL_B},
    )
    if status != 200:
        raise AssertionError(f"ingest failed: HTTP {status} — {payload}")
    if not isinstance(payload, dict) or "analysis_id" not in payload:
        raise AssertionError(f"unexpected ingest payload: {payload}")
    analysis_id = payload["analysis_id"]
    print(f"  OK analysis_id={analysis_id}")

    print("-> GET /api/analysis/{id}")
    status, snap = _request("GET", f"/api/analysis/{analysis_id}")
    if status != 200:
        raise AssertionError(f"analysis fetch failed: HTTP {status}")
    print("  OK")


def test_chat_sse() -> None:
    if not TEST_YT_URL_A or not TEST_YT_URL_B:
        print("-> POST /api/chat SSE (skipped — run ingest test first)")
        return
    print("-> POST /api/ingest for chat test")
    status, payload = _request(
        "POST",
        "/api/ingest",
        {"video_a_url": TEST_YT_URL_A, "video_b_url": TEST_YT_URL_B},
    )
    if status != 200 or not isinstance(payload, dict):
        raise AssertionError(f"ingest for chat failed: {status} {payload}")
    analysis_id = payload["analysis_id"]

    print("-> POST /api/chat (SSE)")
    url = f"{API_URL}/api/chat"
    body = json.dumps({"analysis_id": analysis_id, "message": "Summarize the key differences."}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    tokens = 0
    with urllib.request.urlopen(req, timeout=120) as resp:
        chunk = resp.read(4096).decode("utf-8", errors="replace")
        if "data:" not in chunk and chunk.strip():
            raise AssertionError(f"unexpected chat response: {chunk[:200]!r}")
        tokens = chunk.count('"type": "token"') + chunk.count('"type":"token"')
    print(f"  OK received SSE stream ({len(chunk)} bytes)")


def main() -> int:
    print(f"Vanadium smoke test -> {API_URL}\n")
    tests = [test_health, test_cors, test_ingest_youtube, test_chat_sse]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            failed += 1
            print(f"  FAIL {exc}")
        print()
    if failed:
        print(f"{failed} test(s) failed.")
        return 1
    print("All smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
