import asyncio

import httpx

from collector.live import register_streams, rtsp_url


def test_rtsp_url_escapes_credentials():
    conn = {"host": "10.0.0.5", "port": 554, "rtsp_path": "/s1", "username": "a@b", "password": "p/w:x"}
    assert rtsp_url(conn) == "rtsp://a%40b:p%2Fw%3Ax@10.0.0.5:554/s1"


def test_register_streams_puts_each_camera_and_survives_failure():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.params["name"])
        return httpx.Response(500 if req.url.params["name"] == "BAD" else 200)

    cams = [
        {"code": "CAM-1", "connection": {"host": "h", "username": "u", "password": "p"}},
        {"code": "BAD", "connection": {"host": "h", "username": "u", "password": "p"}},
        {"code": "NOCONN", "connection": None},
    ]

    async def run() -> int:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await register_streams(c, "http://go2rtc:1984", cams)

    assert asyncio.run(run()) == 1 and seen == ["CAM-1", "BAD"]
