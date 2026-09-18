"""接口级测试：覆盖台账、巡查、问题整改、清掏台账与统计看板。"""

from datetime import date, datetime, timedelta

from tests.conftest import full_items


def test_health_and_dictionaries(client):
    assert client.get("/health").json()["status"] == "ok"
    payload = client.get("/api/v1/meta/dictionaries").json()
    assert "待整改" in payload["issue_status"]
    assert len(payload["inspection_check_items"]) == 8
    assert payload["issue_transitions"]["待整改"] == ["整改中", "已关闭"]


def test_restroom_crud_and_delete_guard(client, restroom):
    assert restroom["code"].startswith("WC-")

    listed = client.get("/api/v1/restrooms", params={"district": "测试区"}).json()
    assert listed["meta"]["total"] >= 1

    detail = client.get(f"/api/v1/restrooms/{restroom['id']}").json()
    assert detail["inspection_count"] == 0
    assert detail["open_issue_count"] == 0

    updated = client.patch(
        f"/api/v1/restrooms/{restroom['id']}", json={"status": "维修中", "manager": "新责任人"}
    ).json()
    assert updated["status"] == "维修中"
    assert updated["manager"] == "新责任人"

    # 存在关联数据时不允许直接删除
    client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "测试巡查员",
            "shift": "早班",
            "items": full_items(9),
        },
    )
    blocked = client.delete(f"/api/v1/restrooms/{restroom['id']}")
    assert blocked.status_code == 409

    ok = client.delete(f"/api/v1/restrooms/{restroom['id']}", params={"force": "true"})
    assert ok.status_code == 200
    assert client.get(f"/api/v1/restrooms/{restroom['id']}").status_code == 404


def test_inspection_scoring_and_filter(client, restroom):
    good = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "李巡查",
            "shift": "中班",
            "items": full_items(9),
            "remark": "整体良好",
        },
    ).json()
    assert good["score"] == 90.0
    assert good["grade"] == "优秀"
    assert good["result"] == "正常"

    bad_items = full_items(9)
    bad_items[0]["score"] = 3
    bad_items[0]["remark"] = "地面污渍"
    bad = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "李巡查",
            "shift": "晚班",
            "items": bad_items,
        },
    ).json()
    assert bad["result"] == "发现问题"
    assert bad["score"] < 90

    filtered = client.get(
        "/api/v1/inspections", params={"result": "发现问题", "restroom_id": restroom["id"]}
    ).json()
    assert filtered["meta"]["total"] == 1
    assert filtered["items"][0]["id"] == bad["id"]
    assert filtered["items"][0]["restroom"]["name"] == restroom["name"]

    today = datetime.now().date().isoformat()
    ranged = client.get(
        "/api/v1/inspections", params={"date_from": today, "date_to": today}
    ).json()
    assert ranged["meta"]["total"] == 2

    duplicate = full_items(5) + [{"name": "地面与台阶清洁", "score": 4}]
    rejected = client.post(
        "/api/v1/inspections",
        json={"restroom_id": restroom["id"], "inspector": "李巡查", "items": duplicate},
    )
    assert rejected.status_code == 400

    empty = client.post(
        "/api/v1/inspections",
        json={"restroom_id": restroom["id"], "inspector": "李巡查", "items": []},
    )
    assert empty.status_code == 422


def test_issue_lifecycle(client, restroom):
    inspection = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "王巡查",
            "items": full_items(4),
        },
    ).json()

    issue = client.post(
        "/api/v1/issues",
        json={
            "restroom_id": restroom["id"],
            "inspection_id": inspection["id"],
            "title": "地面污渍未清理",
            "description": "巡查发现地面有明显污渍",
            "category": "保洁不到位",
            "severity": "严重",
            "reporter": "王巡查",
            "assignee": "保洁班组",
            "deadline": (datetime.now() - timedelta(days=1)).isoformat(),
        },
    ).json()
    assert issue["status"] == "待整改"
    assert len(issue["records"]) == 1
    assert issue["records"][0]["action"] == "上报问题"

    # 越级流转被拒绝：待整改 -> 已完成
    invalid = client.post(
        f"/api/v1/issues/{issue['id']}/transitions",
        json={"to_status": "已完成", "operator": "值班长"},
    )
    assert invalid.status_code == 400
    assert "不允许流转" in invalid.json()["detail"]

    options = client.get(f"/api/v1/issues/{issue['id']}/transitions").json()
    assert {option["status"] for option in options} == {"整改中", "已关闭"}

    processing = client.post(
        f"/api/v1/issues/{issue['id']}/transitions",
        json={"to_status": "整改中", "operator": "保洁班组张伟", "remark": "已安排清洗"},
    ).json()
    assert processing["status"] == "整改中"
    assert processing["assignee"] == "保洁班组"

    reviewing = client.post(
        f"/api/v1/issues/{issue['id']}/transitions",
        json={"to_status": "待验收", "operator": "保洁班组张伟", "remark": "整改完成待验收"},
    ).json()
    assert reviewing["status"] == "待验收"

    # 验收驳回回到整改中
    rejected = client.post(
        f"/api/v1/issues/{issue['id']}/transitions",
        json={"to_status": "整改中", "operator": "王巡查", "remark": "角落仍有残留"},
    ).json()
    assert rejected["status"] == "整改中"
    assert rejected["records"][-1]["action"] == "验收驳回"

    for target in ("待验收", "已完成", "已关闭"):
        payload = {"to_status": target, "operator": "值班长", "remark": f"流转到{target}"}
        response = client.post(f"/api/v1/issues/{issue['id']}/transitions", json=payload)
        assert response.status_code == 200, response.text
    final = response.json()
    assert final["status"] == "已关闭"
    assert final["closed_at"] is not None
    assert [record["to_status"] for record in final["records"]][-1] == "已关闭"

    closed_record = client.post(
        f"/api/v1/issues/{issue['id']}/records",
        json={"action": "整改进度", "operator": "值班长", "remark": "补充说明"},
    )
    assert closed_record.status_code == 400

    overdue = client.get("/api/v1/issues", params={"overdue": "true"}).json()
    assert overdue["meta"]["total"] == 0

    # 巡查记录可反查关联问题数量
    detail = client.get(f"/api/v1/inspections/{inspection['id']}").json()
    assert detail["issue_count"] == 1


def test_issue_requires_matching_restroom(client, restroom):
    other = client.post(
        "/api/v1/restrooms",
        json={"name": "另一座公厕", "district": "测试区", "address": "测试路 2 号"},
    ).json()
    inspection = client.post(
        "/api/v1/inspections",
        json={"restroom_id": other["id"], "inspector": "周巡查", "items": full_items(9)},
    ).json()
    mismatch = client.post(
        "/api/v1/issues",
        json={
            "restroom_id": restroom["id"],
            "inspection_id": inspection["id"],
            "title": "关联错误",
        },
    )
    assert mismatch.status_code == 400
    assert "不一致" in mismatch.json()["detail"]


def test_dashboard_stats(client, restroom):
    payload = client.get("/api/v1/stats/dashboard", params={"trend_days": 7}).json()
    overview = payload["overview"]
    assert overview["restroom_total"] >= 1
    assert overview["inspection_total"] >= 1
    assert len(payload["inspection_trend"]) == 7
    assert {item["name"] for item in payload["issue_by_status"]} == {
        "待整改",
        "整改中",
        "待验收",
        "已完成",
        "已关闭",
    }
    assert payload["top_restrooms"]
    assert "rectification_rate" in overview


def test_septic_cleaning_crud(client, restroom):
    # 公厕档案默认含池容、使用频次与推算周期
    assert restroom["septic_capacity"] == 5.0
    assert restroom["usage_frequency"] == "中频"

    created = client.post(
        "/api/v1/septic/cleanings",
        json={
            "restroom_id": restroom["id"],
            "clean_date": "2026-09-01",
            "contractor": "城维环保清掏服务有限公司",
            "volume": 4.2,
            "destination": "北郊污水处理厂污泥处置中心",
            "vehicle_no": "鄂A·8T269",
            "manifest_no": "LD-20260901-001",
            "operator": "王师傅",
            "remark": "例行清掏",
        },
    )
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["code"].startswith("HC-20260901-")
    assert record["restroom"]["name"] == restroom["name"]

    listed = client.get(
        "/api/v1/septic/cleanings",
        params={"keyword": "城维", "restroom_id": restroom["id"]},
    ).json()
    assert listed["meta"]["total"] == 1

    updated = client.patch(
        f"/api/v1/septic/cleanings/{record['id']}", json={"volume": 4.6, "operator": "李师傅"}
    ).json()
    assert updated["volume"] == 4.6
    assert updated["operator"] == "李师傅"

    detail = client.get(f"/api/v1/restrooms/{restroom['id']}").json()
    assert detail["cleaning_count"] == 1
    assert detail["latest_clean_date"] == "2026-09-01"
    assert detail["next_clean_date"] == "2026-11-30"  # 5m³ × 18 / 1.0 = 90 天
    assert detail["septic_cycle_actual"] == 90

    removed = client.delete(f"/api/v1/septic/cleanings/{record['id']}")
    assert removed.status_code == 200
    assert client.get(f"/api/v1/septic/cleanings/{record['id']}").status_code == 404


def test_septic_cycle_formula_and_manual_override(client):
    # 高频 8m³：8 × 18 / 1.6 = 90 天
    high = client.post(
        "/api/v1/restrooms",
        json={
            "name": "高频公厕",
            "district": "测试区",
            "septic_capacity": 8.0,
            "usage_frequency": "高频",
        },
    ).json()
    # 低频 3m³：3 × 18 / 0.6 = 90 天
    low = client.post(
        "/api/v1/restrooms",
        json={
            "name": "低频公厕",
            "district": "测试区",
            "septic_capacity": 3.0,
            "usage_frequency": "低频",
        },
    ).json()
    # 极小池容也不低于 15 天
    tiny = client.post(
        "/api/v1/restrooms",
        json={
            "name": "微型公厕",
            "district": "测试区",
            "septic_capacity": 0.5,
            "usage_frequency": "高频",
        },
    ).json()
    assert client.get(f"/api/v1/restrooms/{high['id']}").json()["septic_cycle_actual"] == 90
    assert client.get(f"/api/v1/restrooms/{low['id']}").json()["septic_cycle_actual"] == 90
    assert client.get(f"/api/v1/restrooms/{tiny['id']}").json()["septic_cycle_actual"] == 15

    # 人工设置周期优先于推算
    patched = client.patch(f"/api/v1/restrooms/{high['id']}", json={"septic_cycle_days": 60}).json()
    assert patched["septic_cycle_days"] == 60
    assert client.get(f"/api/v1/restrooms/{high['id']}").json()["septic_cycle_actual"] == 60


def test_septic_schedule_overdue_and_due_soon(client, restroom):
    today = date.today()

    def schedule_of(restroom_id):
        rows = client.get("/api/v1/septic/schedules").json()
        return next(item for item in rows if item["restroom"]["id"] == restroom_id)

    # 从无记录 → 未建档
    schedule = schedule_of(restroom["id"])
    assert schedule["status"] == "未建档"
    assert schedule["next_clean_date"] is None

    # 100 天前清掏，周期 90 天 → 已超期
    client.post(
        "/api/v1/septic/cleanings",
        json={
            "restroom_id": restroom["id"],
            "clean_date": (today - timedelta(days=100)).isoformat(),
            "contractor": "绿源粪污清运有限公司",
            "volume": 4.0,
            "destination": "南郊有机废弃物处理站",
        },
    )
    schedule = schedule_of(restroom["id"])
    assert schedule["status"] == "已超期"
    assert schedule["days_remaining"] == -10

    overdue_ids = {
        item["restroom"]["id"]
        for item in client.get("/api/v1/septic/schedules", params={"overdue_only": "true"}).json()
    }
    assert restroom["id"] in overdue_ids

    # 85 天前清掏 → 还剩 5 天，提前 7 天提醒 → 即将到期
    client.post(
        "/api/v1/septic/cleanings",
        json={
            "restroom_id": restroom["id"],
            "clean_date": (today - timedelta(days=85)).isoformat(),
            "contractor": "绿源粪污清运有限公司",
            "volume": 4.0,
            "destination": "南郊有机废弃物处理站",
        },
    )
    schedule = schedule_of(restroom["id"])
    assert schedule["status"] == "即将到期"
    assert schedule["days_remaining"] == 5

    overview = client.get("/api/v1/septic/overview").json()
    assert overview["due_soon_count"] >= 1
    assert overview["cleaning_total"] >= 2


def test_septic_cleaning_delete_guard(client, restroom):
    client.post(
        "/api/v1/septic/cleanings",
        json={
            "restroom_id": restroom["id"],
            "clean_date": "2026-08-01",
            "contractor": "洁通管道清掏有限公司",
            "volume": 3.5,
            "destination": "城东粪污集中处理站",
        },
    )
    blocked = client.delete(f"/api/v1/restrooms/{restroom['id']}")
    assert blocked.status_code == 409
    assert "清掏记录" in blocked.json()["detail"]

    forced = client.delete(f"/api/v1/restrooms/{restroom['id']}", params={"force": "true"})
    assert forced.status_code == 200
    assert client.get("/api/v1/septic/cleanings", params={"restroom_id": restroom["id"]}).json()[
        "meta"
    ]["total"] == 0
