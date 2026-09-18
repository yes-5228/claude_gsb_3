"""化粪池清掏与排污外运接口测试。"""

from datetime import datetime, timedelta


def _make_restroom(client, name: str, *, with_tank: bool = True) -> dict:
    payload = {
        "name": name,
        "district": "测试区",
        "address": "测试路 1 号",
        "grade": "二类",
        "status": "正常开放",
        "manager": "测试员",
    }
    if with_tank:
        # 池容 10m³、日均 500 人次 → 推算周期 10*0.8/(500*0.0004) = 40 天
        payload.update({"tank_capacity": 10.0, "usage_frequency": 500})
    response = client.post("/api/v1/restrooms", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _create_cleaning(client, restroom_id: int, days_ago: float = 0, **overrides):
    payload = {
        "restroom_id": restroom_id,
        "clean_time": (datetime.now() - timedelta(days=days_ago)).isoformat(),
        "operator_unit": "城环清掏服务队",
        "volume": 8.5,
        "destination": "市第一污水处理厂",
    }
    payload.update(overrides)
    return client.post("/api/v1/cleanings", json=payload)


def test_cleaning_crud_and_validation(client, restroom):
    created = _create_cleaning(client, restroom["id"], remark="罐车浙A12345")
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["operator_unit"] == "城环清掏服务队"
    assert record["volume"] == 8.5
    assert record["restroom"]["name"] == restroom["name"]

    listed = client.get("/api/v1/cleanings", params={"restroom_id": restroom["id"]}).json()
    assert listed["meta"]["total"] == 1
    by_keyword = client.get("/api/v1/cleanings", params={"keyword": "城环"}).json()
    assert by_keyword["meta"]["total"] == 1
    by_unit = client.get("/api/v1/cleanings", params={"operator_unit": "清掏"}).json()
    assert by_unit["meta"]["total"] == 1

    detail = client.get(f"/api/v1/cleanings/{record['id']}").json()
    assert detail["destination"] == "市第一污水处理厂"

    updated = client.patch(
        f"/api/v1/cleanings/{record['id']}",
        json={"volume": 9.2, "destination": "城东污泥消纳场"},
    ).json()
    assert updated["volume"] == 9.2
    assert updated["destination"] == "城东污泥消纳场"

    assert client.delete(f"/api/v1/cleanings/{record['id']}").status_code == 200
    assert client.get(f"/api/v1/cleanings/{record['id']}").status_code == 404

    # 参数校验：清掏量必须为正、作业单位必填、清掏时间不可为未来、公厕必须存在
    assert _create_cleaning(client, restroom["id"], volume=0).status_code == 422
    assert _create_cleaning(client, restroom["id"], operator_unit="").status_code == 422
    assert _create_cleaning(client, restroom["id"], destination="").status_code == 422
    future = (datetime.now() + timedelta(days=1)).isoformat()
    assert _create_cleaning(client, restroom["id"], clean_time=future).status_code == 400
    assert _create_cleaning(client, 999999).status_code == 404


def test_cleaning_schedule_cycle_and_overdue_list(client):
    normal = _make_restroom(client, "正常公厕")
    due_soon = _make_restroom(client, "临期公厕")
    overdue = _make_restroom(client, "超期公厕")
    unset = _make_restroom(client, "未设置公厕", with_tank=False)

    _create_cleaning(client, normal["id"], days_ago=1)
    _create_cleaning(client, due_soon["id"], days_ago=36)  # 40 天周期，剩余 4 天
    _create_cleaning(client, overdue["id"], days_ago=45)  # 已超期 5 天

    schedule = client.get("/api/v1/cleanings/schedule").json()
    by_id = {row["restroom_id"]: row for row in schedule}

    assert by_id[normal["id"]]["status"] == "正常"
    assert by_id[normal["id"]]["cycle_days"] == 40
    assert by_id[normal["id"]]["clean_count"] == 1
    assert by_id[due_soon["id"]]["status"] == "临期"
    assert by_id[due_soon["id"]]["days_remaining"] == 4
    assert by_id[overdue["id"]]["status"] == "已超期"
    assert by_id[overdue["id"]]["days_remaining"] == -5
    assert by_id[unset["id"]]["status"] == "未设置"
    assert by_id[unset["id"]]["cycle_days"] is None

    # 超期公厕单独列出，且在完整清单中排在最前
    overdue_only = client.get("/api/v1/cleanings/schedule", params={"status": "已超期"}).json()
    assert [row["restroom_id"] for row in overdue_only] == [overdue["id"]]
    assert schedule[0]["status"] == "已超期"

    # 看板统计同步反映
    overview = client.get("/api/v1/stats/overview").json()
    assert overview["cleaning_overdue"] == 1
    assert overview["cleaning_due_soon"] == 1
    dashboard = client.get("/api/v1/stats/dashboard").json()
    reminder_ids = {row["restroom_id"] for row in dashboard["cleaning_reminders"]}
    assert reminder_ids == {overdue["id"], due_soon["id"]}


def test_schedule_uses_created_at_when_never_cleaned(client):
    room = _make_restroom(client, "从未清掏公厕")
    schedule = client.get("/api/v1/cleanings/schedule").json()
    item = next(row for row in schedule if row["restroom_id"] == room["id"])
    # 无清掏记录时自建档时间起算：刚建档 → 正常，且累计 0 次
    assert item["status"] == "正常"
    assert item["clean_count"] == 0
    assert item["last_clean_time"] is None

    # 补登一条清掏记录后转为按清掏时间推算
    _create_cleaning(client, room["id"], days_ago=39)  # 剩余 1 天 → 临期
    refreshed = client.get("/api/v1/cleanings/schedule").json()
    item = next(row for row in refreshed if row["restroom_id"] == room["id"])
    assert item["status"] == "临期"
    assert item["clean_count"] == 1


def test_restroom_tank_fields_roundtrip(client):
    room = _make_restroom(client, "池容公厕")
    assert room["tank_capacity"] == 10.0
    assert room["usage_frequency"] == 500

    updated = client.patch(
        f"/api/v1/restrooms/{room['id']}", json={"tank_capacity": 15.5, "usage_frequency": 800}
    ).json()
    assert updated["tank_capacity"] == 15.5
    assert updated["usage_frequency"] == 800

    # 周期随档案联动：15.5*0.8/(800*0.0004) = 38.75 → 39 天
    schedule = client.get("/api/v1/cleanings/schedule").json()
    item = next(row for row in schedule if row["restroom_id"] == room["id"])
    assert item["cycle_days"] == 39

    rejected = client.patch(f"/api/v1/restrooms/{room['id']}", json={"tank_capacity": -1})
    assert rejected.status_code == 422
