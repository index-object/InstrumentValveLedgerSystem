# coding=utf-8
"""维护记录与设备关联自愈的回归测试。

背景：维护记录与设备之间只保存 ``device_type + device_id``（自增主键）：

* 设备被删除时记录只被标记 ``valve_deleted=True``，设备再以相同
  「装置名称 + 设备位号」重建后会拿到新主键，旧记录永远挂不回新设备；
* 检修记录导出 Excel 后重新导入时，若设备已删除或仍处于草稿状态，
  该行会落成 ``device_type=''``、``device_id=0`` 的孤儿记录。

这里锁定修复后的行为：记录按天然键（装置名称 + 设备位号）自动重新
关联，无需人工逐条重挂。
"""

import io

import pandas as pd

from app import db
from app.models import User, Ledger, MaintenanceRecord
from app.devices.types.control_valve import ControlValve
from app.devices.types.pressure_transmitter import PressureTransmitter
from app.devices.valve_helper import handle_maintenance_on_valve_delete
from app.utils.device_lookup import resolve_type_code
from app.utils.maintenance_link import (
    find_device_by_tag,
    is_orphan,
    link_record,
    relink_orphan_maintenance_records,
)


def _login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def _seed_valve_with_record(app, status="approved"):
    """建一个已审批阀门 + 一条关联维护记录，返回 (valve_id, record_id)。"""
    with app.app_context():
        user = User.query.filter_by(username="user1").first()
        valve = ControlValve(
            装置名称="气化装置", 位号="CV-001", 名称="进料调节阀",
            status=status, created_by=user.id,
        )
        db.session.add(valve)
        db.session.flush()
        record = MaintenanceRecord(
            device_type="control_valve", device_id=valve.id,
            装置名称="气化装置", 设备位号="CV-001", 设备名称="进料调节阀",
            检修内容="更换填料", 检修人员="张三", created_by=user.id,
        )
        db.session.add(record)
        db.session.commit()
        return valve.id, record.id


# ========== 问题一：阀门删除后重建，旧记录自动挂回 ==========


def test_recreated_valve_relinks_record_on_maintenance_list(app, client, init_database):
    """阀门删除再以相同位号重建后，打开维护记录列表应自动恢复关联"""
    old_valve_id, record_id = _seed_valve_with_record(app)

    with app.app_context():
        user = User.query.filter_by(username="user1").first()
        valve = ControlValve.query.get(old_valve_id)
        handle_maintenance_on_valve_delete("control_valve", valve.id, None)
        db.session.delete(valve)
        db.session.commit()

        # SQLite 会复用被删掉的最大主键，先插一台无关设备占位，
        # 保证重建后的阀门确实拿到不同的 id（否则测不出真实问题）
        db.session.add(ControlValve(
            装置名称="气化装置", 位号="FILLER-001", 名称="占位阀",
            status="approved", created_by=user.id,
        ))
        db.session.commit()

        recreated = ControlValve(
            装置名称="气化装置", 位号="CV-001", 名称="进料调节阀",
            status="approved", created_by=user.id,
        )
        db.session.add(recreated)
        db.session.commit()
        new_valve_id = recreated.id

        # 删除后、重建前：记录确实处于失联状态
        record = MaintenanceRecord.query.get(record_id)
        assert record.valve_deleted is True
        assert new_valve_id != old_valve_id

    _login(client, "user1", "user123")
    assert client.get("/maintenance").status_code == 200

    with app.app_context():
        record = MaintenanceRecord.query.get(record_id)
        assert record.device_type == "control_valve"
        assert record.device_id == new_valve_id
        assert record.valve_deleted is False


def test_valve_create_route_relinks_record(app, client, init_database):
    """通过 /valve/new 重建阀门时，创建动作本身就把旧记录挂回"""
    with app.app_context():
        user = User.query.filter_by(username="user1").first()
        record = MaintenanceRecord(
            device_type="control_valve", device_id=999,
            装置名称="气化装置", 设备位号="CV-009", 设备名称="旧阀",
            检修内容="旧检修", created_by=user.id, valve_deleted=True,
        )
        ledger = Ledger(名称="重建台账", 类型="control_valve", created_by=user.id)
        db.session.add_all([record, ledger])
        db.session.commit()
        record_id, ledger_id = record.id, ledger.id

    _login(client, "user1", "user123")
    resp = client.post("/valve/new", data={
        "ledger_id": str(ledger_id),
        "装置名称": "气化装置",
        "位号": "CV-009",
        "名称": "新阀",
    })
    assert resp.status_code in (200, 302)

    with app.app_context():
        valve = ControlValve.query.filter_by(位号="CV-009").first()
        record = MaintenanceRecord.query.get(record_id)
        assert valve is not None
        assert record.device_id == valve.id
        assert record.valve_deleted is False


# ========== 问题二：检修记录导出后删除再导入，自动关联 ==========


def _export_then_import(app, client, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    resp = client.get("/maintenance/export")
    assert resp.status_code == 200
    return resp.data


def test_export_reimport_relinks_to_existing_valve(app, client, init_database, tmp_path):
    """导出 → 删除 → 重新导入，记录应关联回原阀门"""
    _, record_id = _seed_valve_with_record(app)
    _login(client, "user1", "user123")

    exported = _export_then_import(app, client, tmp_path)
    df = pd.read_excel(io.BytesIO(exported))
    assert not df.empty and df.to_dict("records")[0]["设备类型"] == "调节阀"

    with app.app_context():
        db.session.delete(MaintenanceRecord.query.get(record_id))
        db.session.commit()

    client.post(
        "/maintenance/import/upload",
        data={"file": (io.BytesIO(exported), "维护记录.xlsx")},
        content_type="multipart/form-data",
    )
    client.post("/maintenance/import/execute", data={"unmatched_action": "skip"})

    with app.app_context():
        valve = ControlValve.query.filter_by(位号="CV-001").first()
        record = MaintenanceRecord.query.filter_by(设备位号="CV-001").first()
        assert record is not None
        assert record.device_type == "control_valve"
        assert record.device_id == valve.id
        assert record.valve_deleted is False


def test_reimport_links_draft_device(app, client, init_database, tmp_path):
    """设备仍是草稿时，import 匹配不到，导入后也要按天然键自愈关联"""
    _, record_id = _seed_valve_with_record(app)
    _login(client, "user1", "user123")
    exported = _export_then_import(app, client, tmp_path)

    with app.app_context():
        db.session.delete(MaintenanceRecord.query.get(record_id))
        valve = ControlValve.query.filter_by(位号="CV-001").first()
        valve.status = "draft"
        db.session.commit()
        valve_id = valve.id

    # 草稿设备被 resolve_device 排除，预览阶段会落到未匹配
    client.post(
        "/maintenance/import/upload",
        data={"file": (io.BytesIO(exported), "维护记录.xlsx")},
        content_type="multipart/form-data",
    )
    # 选择"保留未匹配行"，导入后再自愈
    client.post("/maintenance/import/execute", data={"unmatched_action": "keep"})

    with app.app_context():
        record = MaintenanceRecord.query.filter_by(设备位号="CV-001").first()
        assert record is not None
        assert record.device_id == valve_id
        assert record.valve_deleted is False


def test_import_prefers_device_type_hint(app, init_database):
    """同（装置，位号）多类型重名时，用导出的「设备类型」列消歧"""
    with app.app_context():
        user = User.query.filter_by(username="user1").first()
        db.session.add_all([
            ControlValve(装置名称="气化装置", 位号="TAG-1", 名称="阀",
                         status="approved", created_by=user.id),
            PressureTransmitter(装置名称="气化装置", 位号="TAG-1", 设备名称="表",
                                status="approved", created_by=user.id),
        ])
        db.session.commit()

        record = MaintenanceRecord(
            device_type="pressure_transmitter", device_id=999,
            装置名称="气化装置", 设备位号="TAG-1", 设备名称="表",
            检修内容="校准", created_by=user.id, valve_deleted=True,
        )
        db.session.add(record)
        db.session.commit()
        record_id = record.id

        from app.utils.device_lookup import resolve_device
        # 无类型提示时存在歧义
        assert len(resolve_device("气化装置", "TAG-1")) == 2
        # 带类型提示时命中唯一类型
        hinted = resolve_device("气化装置", "TAG-1", type_hint="pressure_transmitter")
        assert len(hinted) == 1 and hinted[0][0] == "pressure_transmitter"

        link_record(record)
        db.session.commit()
        record = MaintenanceRecord.query.get(record_id)
        device = PressureTransmitter.query.filter_by(位号="TAG-1").first()
        assert record.device_type == "pressure_transmitter"
        assert record.device_id == device.id


# ========== 非阀门仪表：删除标记 + 重建挂回 ==========


def test_non_valve_delete_marks_record_and_recreate_relinks(app, client, init_database):
    """删除其他仪表时也要把维护记录标记为已删除，重建后自动挂回"""
    with app.app_context():
        user = User.query.filter_by(username="user1").first()
        device = PressureTransmitter(
            装置名称="气化装置", 位号="PT-001", 设备名称="压力变送器",
            status="approved", created_by=user.id,
        )
        db.session.add(device)
        db.session.flush()
        record = MaintenanceRecord(
            device_type="pressure_transmitter", device_id=device.id,
            装置名称="气化装置", 设备位号="PT-001", 设备名称="压力变送器",
            检修内容="校准", created_by=user.id,
        )
        db.session.add(record)
        db.session.commit()
        device_id, record_id = device.id, record.id

    _login(client, "user1", "user123")
    assert client.post(f"/device/pressure_transmitter/{device_id}/delete").status_code in (200, 302)

    with app.app_context():
        record = MaintenanceRecord.query.get(record_id)
        assert record is not None, "删除设备不应连维护记录一起删掉"
        assert record.valve_deleted is True

    # 以相同（装置，位号）重建 -> 创建动作直接挂回
    client.post("/device/pressure_transmitter/new", data={
        "装置名称": "气化装置", "位号": "PT-001", "设备名称": "压力变送器",
    })
    with app.app_context():
        new_device = PressureTransmitter.query.filter_by(位号="PT-001").first()
        record = MaintenanceRecord.query.get(record_id)
        assert new_device is not None
        assert record.device_id == new_device.id
        assert record.valve_deleted is False


# ========== 工具函数 ==========


def test_find_device_by_tag_ambiguous_without_hint(app, init_database):
    with app.app_context():
        user = User.query.filter_by(username="user1").first()
        db.session.add_all([
            ControlValve(装置名称="气化装置", 位号="TAG-2", status="approved",
                         created_by=user.id),
            PressureTransmitter(装置名称="气化装置", 位号="TAG-2", status="approved",
                                created_by=user.id),
        ])
        db.session.commit()
        assert find_device_by_tag("气化装置", "TAG-2") is None
        assert find_device_by_tag("气化装置", "TAG-2", type_hint="control_valve")[0] == "control_valve"


def test_find_device_by_tag_unit_empty_falls_back_to_tag(app, init_database):
    with app.app_context():
        user = User.query.filter_by(username="user1").first()
        db.session.add(ControlValve(装置名称="气化装置", 位号="TAG-3",
                                    status="approved", created_by=user.id))
        db.session.commit()
        match = find_device_by_tag("", "TAG-3")
        assert match is not None and match[0] == "control_valve"


def test_relink_skips_healthy_records(app, init_database):
    with app.app_context():
        user = User.query.filter_by(username="user1").first()
        valve = ControlValve(装置名称="气化装置", 位号="TAG-4",
                             status="approved", created_by=user.id)
        db.session.add(valve)
        db.session.flush()
        record = MaintenanceRecord(device_type="control_valve", device_id=valve.id,
                                   装置名称="气化装置", 设备位号="TAG-4",
                                   created_by=user.id)
        db.session.add(record)
        db.session.commit()
        assert relink_orphan_maintenance_records() == 0


def test_resolve_type_code_accepts_code_and_name():
    assert resolve_type_code("control_valve") == "control_valve"
    assert resolve_type_code("调节阀") == "control_valve"
    assert resolve_type_code("不存在的类型") is None
    assert resolve_type_code("") is None


def test_relink_handles_dangling_id_without_delete_flag(app, init_database):
    """历史遗留数据：设备被硬删、记录既没标记删除也没被改过，也要能自愈"""
    with app.app_context():
        user = User.query.filter_by(username="user1").first()
        valve = ControlValve(装置名称="气化装置", 位号="TAG-5",
                             status="approved", created_by=user.id)
        db.session.add(valve)
        db.session.flush()
        record = MaintenanceRecord(device_type="control_valve", device_id=valve.id,
                                   装置名称="气化装置", 设备位号="TAG-5",
                                   created_by=user.id)
        db.session.add(record)
        db.session.commit()
        record_id = record.id

        db.session.delete(valve)
        db.session.commit()
        # 占位一台无关设备，避免 SQLite 复用主键，确保新设备 id 不同
        db.session.add(ControlValve(装置名称="气化装置", 位号="FILLER-5",
                                    status="approved", created_by=user.id))
        db.session.commit()
        rebuilt = ControlValve(装置名称="气化装置", 位号="TAG-5",
                               status="approved", created_by=user.id)
        db.session.add(rebuilt)
        db.session.commit()
        rebuilt_id = rebuilt.id
        assert rebuilt_id != valve.id

        record = MaintenanceRecord.query.get(record_id)
        assert is_orphan(record) is True
        assert relink_orphan_maintenance_records(records=[record]) == 1
        assert record.device_id == rebuilt_id


def test_reused_id_with_other_tag_is_treated_as_orphan(app, init_database):
    """自增主键被别的设备复用后，记录不能被误判为仍然有效"""
    with app.app_context():
        user = User.query.filter_by(username="user1").first()
        valve = ControlValve(装置名称="气化装置", 位号="OLD-1",
                             status="approved", created_by=user.id)
        db.session.add(valve)
        db.session.flush()
        record = MaintenanceRecord(device_type="control_valve", device_id=valve.id,
                                   装置名称="气化装置", 设备位号="OLD-1",
                                   created_by=user.id)
        db.session.add(record)
        db.session.commit()
        old_id = valve.id

        db.session.delete(valve)
        db.session.commit()
        other = ControlValve(装置名称="气化装置", 位号="NEW-1",
                             status="approved", created_by=user.id)
        db.session.add(other)
        db.session.commit()

        assert other.id == old_id, "SQLite 复用主键，本用例才有意义"
        assert is_orphan(record) is True
        # 位号 OLD-1 已不存在，保持孤儿状态而不是挂到 NEW-1
        assert link_record(record) is False
        assert record.device_id == old_id
