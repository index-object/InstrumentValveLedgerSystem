from app.devices import DeviceTypeRegistry

VALVE_TYPES = ["control_valve", "onoff_valve", "electric_valve"]


def get_valve_model(ledger_or_type):
    """根据台账或类型编码获取对应的阀门模型类"""
    if isinstance(ledger_or_type, str):
        type_code = ledger_or_type
    else:
        type_code = ledger_or_type.类型
    config = DeviceTypeRegistry.get(type_code)
    return config.model_class if config else None


def get_all_valve_models():
    """获取所有阀门模型类列表"""
    models = []
    for code in VALVE_TYPES:
        config = DeviceTypeRegistry.get(code)
        if config and config.model_class:
            models.append(config.model_class)
    return models


def query_valves(ledger_id, status=None):
    """跨两个阀门表查询"""
    results = []
    for model in get_all_valve_models():
        q = model.query.filter_by(ledger_id=ledger_id)
        if status:
            q = q.filter(model.status == status)
        results.extend(q.all())
    results.sort(key=lambda v: v.id or 0, reverse=True)
    return results


def count_valves(ledger_id, status=None):
    """统计两个阀门表的记录数"""
    total = 0
    for model in get_all_valve_models():
        q = model.query.filter_by(ledger_id=ledger_id)
        if status:
            q = q.filter(model.status == status)
        total += q.count()
    return total


def count_valves_by_status(ledger_id):
    """统计各种状态的阀门数量"""
    counts = {"total": 0, "pending": 0, "approved": 0, "rejected": 0, "draft": 0}
    for model in get_all_valve_models():
        base = model.query.filter_by(ledger_id=ledger_id)
        counts["total"] += base.count()
        counts["pending"] += base.filter_by(status="pending").count()
        counts["approved"] += base.filter_by(status="approved").count()
        counts["rejected"] += base.filter_by(status="rejected").count()
        counts["draft"] += base.filter_by(status="draft").count()
    return counts


def get_valve_by_id(valve_id, model_class=None):
    """跨两个表查找阀门，可指定模型类精确查找"""
    if model_class:
        return model_class.query.get(valve_id)
    for model in get_all_valve_models():
        valve = model.query.get(valve_id)
        if valve:
            return valve
    return None


def has_duplicate_tag(tag, exclude_id=None, unit_name=None):
    """检查位号是否重复（兼容旧接口，内部调用 check_duplicate）"""
    from app.utils.duplicate_check import check_duplicate
    for model in get_all_valve_models():
        if check_duplicate(model, unit_name, tag, exclude_id):
            return True
    return False


def get_valve_ledger_type(valve):
    """获取阀门实例对应的台账类型编码"""
    for code in VALVE_TYPES:
        config = DeviceTypeRegistry.get(code)
        if config and config.model_class and isinstance(valve, config.model_class):
            return code
    return None


def handle_maintenance_on_valve_delete(device_type, device_id, delete_maintenance):
    """删除阀门时处理关联的维护记录"""
    from app.models import MaintenanceRecord
    if delete_maintenance and delete_maintenance != "0":
        MaintenanceRecord.query.filter_by(
            device_type=device_type, device_id=device_id
        ).delete()
    else:
        MaintenanceRecord.query.filter_by(
            device_type=device_type, device_id=device_id
        ).update({"valve_deleted": True})
