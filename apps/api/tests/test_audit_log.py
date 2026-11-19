"""The audit log viewer: admins read it, nobody else does, and paging is stable."""


async def test_admin_reads_audit_rows_with_filters_and_paging(admin, supervisor, anon):
    for i in range(3):
        r = await admin.post("/cameras/test-source", json={"name": f"Audit cam {i}"})
        assert r.status_code == 201, r.text

    r = await admin.get("/audit-logs?action=camera.create_test_source&limit=2")
    assert r.status_code == 200, r.text
    rows, meta = r.json()["data"], r.json()["meta"]
    assert len(rows) == 2 and meta["next_before_id"] == rows[-1]["id"]
    assert rows[0]["actor"]["email"] == "admin@stitchsense.local" and rows[0]["entity"] == "device"
    assert rows[0]["id"] > rows[1]["id"]  # newest first

    older = (await admin.get(f"/audit-logs?action=camera.create_test_source&limit=50&before_id={meta['next_before_id']}")).json()
    assert all(x["id"] < meta["next_before_id"] for x in older["data"])

    assert (await admin.get("/audit-logs?entity=no-such-entity")).json()["data"] == []
    assert (await admin.get("/audit-logs?limit=1000")).status_code == 400  # page size is capped
    assert (await supervisor.get("/audit-logs")).status_code == 403
    assert (await anon.get("/audit-logs")).status_code == 401
