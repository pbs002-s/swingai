import asyncio

import httpx

from collector.live import mask_filter, privacy_boxes, register_streams, rtsp_url, stream_source


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


def test_privacy_zones_become_black_boxes_that_cover_the_polygon():
    zones = [
        {"kind": "work", "points": [[0, 0], [1, 0], [1, 1]]},  # work zones are never masked
        {"kind": "privacy", "points": [[0.2, 0.3], [0.5, 0.3], [0.4, 0.6]]},
        {"kind": "privacy", "points": [[0.9, 0.9], [1.2, 0.9], [1.0, 1.0]]},  # out of range is clamped
    ]
    boxes = privacy_boxes(zones)
    assert boxes[0] == (0.2, 0.3, 0.3, 0.3)
    assert boxes[1][0] + boxes[1][2] <= 1.0001
    flt = mask_filter(boxes)
    assert flt.count("drawbox") == 2 and " " not in flt and "t=fill" in flt


def test_masked_camera_is_never_served_raw_and_has_no_audio():
    conn = {"host": "h", "username": "u", "password": "secret"}
    plain = stream_source({"connection": conn, "zones": []})
    assert plain.startswith("rtsp://")
    masked = stream_source({"connection": conn, "zones": [{"kind": "privacy", "points": [[0, 0], [1, 0], [1, 1]]}]})
    assert (
        masked.startswith("exec:ffmpeg") and "drawbox" in masked and " -an " in masked and masked.endswith("{output}")
    )


def test_a_broken_zone_does_not_register_a_raw_stream():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.params["src"])
        return httpx.Response(200)

    bad = {
        "code": "C",
        "connection": {"host": "h"},
        "zones": [{"kind": "privacy", "points": [["x", 0], [1, 0], [1, 1]]}],
    }

    async def run() -> int:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await register_streams(c, "http://go2rtc:1984", [bad])

    assert asyncio.run(run()) == 0 and seen == []
