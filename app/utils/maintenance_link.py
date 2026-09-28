# coding=utf-8
"""维护记录与设备的关联自愈。

维护记录与设备之间只保存了 ``device_type + device_id``（自增主键）这一条
弱关联，一旦设备被删除再重建，关联就会永久断开：

* 删除设备时记录虽然保留了「装置名称 + 设备位号」快照，但旧记录的
  ``device_id`` 指向的是已删除设备的主键，设备以相同位号重建后会拿到
  新主键，旧记录再也挂不回去；
* 检修记录导出 Excel 后，如果重新导入时对应设备缺失（或仍是草稿状态
  被匹配逻辑排除），该行会落成 ``device_type=''``、``device_id=0``、
  ``valve_deleted=True`` 的孤儿记录。

两者的共同点是记录里仍保留着「装置名称 + 设备位号」这个天然键。本模块
按天然键把孤儿记录重新挂回现有设备，使设备恢复后记录能自动关联，无需
人工逐条重挂。
"""

from sqlalchemy import func, or_

from app.models import MaintenanceRecord, db
from app.devices import DeviceTypeRegistry
from app.devices.valve_helper import is_valve_type


def _norm(value):
    """统一成去空白的字符串，``None`` 视作空串。"""
    return value.strip() if isinstance(value, str) else ""


def _device_name(device, device_type):
    """取设备名称字段：阀门是「名称」，其他仪表是「设备名称」。"""
    field = "名称" if is_valve_type(device_type) else "设备名称"
    return getattr(device, field, "") or ""


def device_type_label(device_type):
    """设备类型的显示名（导出用），未知类型返回空串。"""
    config = DeviceTypeRegistry.get(device_type) if device_type else None
    return config.name if config else ""


def find_device_by_id(device_type, device_id):
    """按类型与主键取设备，取不到（已删除 / 类型非法）返回 ``None``。"""
    config = DeviceTypeRegistry.get(device_type) if device_type else None
    if not config or not config.model_class or not device_id:
        return None
    return config.model_class.query.get(device_id)


def is_orphan(record):
    """判断记录是否已和设备失去有效关联。

    除了「未标记删除 / 类型或主键缺失」，还要防止自增主键被回收后记录
    误指向另一台设备：设备位号对不上同样视为失联。
    """
    if record.valve_deleted or not record.device_type or not record.device_id:
        return True
    device = find_device_by_id(record.device_type, record.device_id)
    if device is None:
        return True
    record_tag = _norm(record.设备位号)
    return bool(record_tag) and _norm(getattr(device, "位号", "")) != record_tag


def _collect_candidates(tags):
    """按位号批量取候选设备，返回 ``{位号: [(类型, 设备实例), ...]}``。

    一次查询每个设备表，避免逐条记录 × 逐个类型地查库。
    """
    index = {}
    tags = [tag for tag in tags if tag]
    if not tags:
        return index
    for config in DeviceTypeRegistry.all():
        model = config.model_class
        if not model or not hasattr(model, "位号"):
            continue
        for device in model.query.filter(func.trim(model.位号).in_(tags)).all():
            tag = _norm(getattr(device, "位号", ""))
            index.setdefault(tag, []).append((config.code, device))
    return index


def _pick_candidate(candidates, unit_name, type_hint=None, record_type=None):
    """从候选设备中选出唯一匹配；存在歧义时返回 ``None``。

    装置名称任一方为空时按位号兜底；同一（装置，位号）在多个类型下重名时，
    优先用显式 ``type_hint`` 或记录原有 ``record_type`` 消歧。
    """
    unit = _norm(unit_name)
    filtered = []
    for code, device in candidates:
        device_unit = _norm(getattr(device, "装置名称", ""))
        # 装置名称任一方为空时视为通配，否则必须一致
        if unit and device_unit and device_unit != unit:
            continue
        filtered.append((code, device))

    if not filtered:
        return None
    if len(filtered) > 1:
        for hint in (type_hint, record_type):
            narrowed = [item for item in filtered if item[0] == hint]
            if len(narrowed) == 1:
                filtered = narrowed
                break
        else:
            return None
    device_type, device = filtered[0]
    return device_type, device.id, _device_name(device, device_type)


def find_device_by_tag(unit_name, tag, type_hint=None, record_type=None):
    """按「装置名称 + 设备位号」查找唯一设备。

    :return: ``(device_type, device_id, device_name)`` 或 ``None``
    """
    tag = _norm(tag)
    if not tag:
        return None
    candidates = _collect_candidates([tag]).get(tag, [])
    return _pick_candidate(candidates, unit_name,
                           type_hint=type_hint, record_type=record_type)


def _apply_match(record, match):
    device_type, device_id, device_name = match
    record.device_type = device_type
    record.device_id = device_id
    if device_name:
        record.设备名称 = device_name
    record.valve_deleted = False


def link_record(record, type_hint=None):
    """尝试把单条孤儿记录重新关联到设备，成功返回 ``True``。"""
    if not is_orphan(record):
        return False
    match = find_device_by_tag(
        record.装置名称,
        record.设备位号,
        type_hint=type_hint,
        record_type=record.device_type,
    )
    if not match:
        return False
    _apply_match(record, match)
    return True


def orphan_query():
    """疑似孤儿记录的查询：被标记删除、类型或主键缺失的记录。"""
    return MaintenanceRecord.query.filter(
        or_(
            MaintenanceRecord.valve_deleted.is_(True),
            MaintenanceRecord.device_type.is_(None),
            MaintenanceRecord.device_type == "",
            MaintenanceRecord.device_id.is_(None),
            MaintenanceRecord.device_id == 0,
        )
    )


def relink_orphan_maintenance_records(records=None, commit=True):
    """批量重新关联孤儿维护记录，返回成功条数。

    :param records: 待检查的记录；默认扫描全部疑似孤儿记录
    :param commit: 是否在有关联变化时提交事务
    """
    targets = records if records is not None else orphan_query().all()
    index = _collect_candidates({_norm(record.设备位号) for record in targets})

    count = 0
    for record in targets:
        if not is_orphan(record):
            continue
        match = _pick_candidate(
            index.get(_norm(record.设备位号), []),
            record.装置名称,
            record_type=record.device_type,
        )
        if not match:
            continue
        _apply_match(record, match)
        count += 1
    if count and commit:
        db.session.commit()
    return count


def relink_records_for_device(device, device_type, commit=True):
    """设备（重新）创建后，把同（装置，位号）的孤儿记录直接挂回该设备。

    这里已经拿着目标设备实例，直接赋值即可，不再走按位号反查，避免同
    位号多类型时挂错。
    """
    tag = _norm(getattr(device, "位号", ""))
    if not tag or not device.id:
        return 0
    unit = _norm(getattr(device, "装置名称", ""))
    device_name = _device_name(device, device_type)
    targets = orphan_query().filter(
        func.trim(MaintenanceRecord.设备位号) == tag
    ).all()

    count = 0
    for record in targets:
        record_unit = _norm(record.装置名称)
        if record_unit and unit and record_unit != unit:
            continue
        record.device_type = device_type
        record.device_id = device.id
        if device_name:
            record.设备名称 = device_name
        record.valve_deleted = False
        count += 1
    if count and commit:
        db.session.commit()
    return count
