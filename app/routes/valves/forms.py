import json
from app.models import ValveAttachment, Setting, Valve, Ledger, db
from datetime import datetime


def update_ledger_status(ledger):
    total = Valve.query.filter_by(ledger_id=ledger.id).count()
    if total == 0:
        return
    approved = Valve.query.filter_by(ledger_id=ledger.id, status="approved").count()
    if approved == total:
        ledger.status = "approved"
        ledger.approved_at = datetime.utcnow()


VALVE_FIELD_NAMES = [
    "装置名称",
    "位号",
    "名称",
    "设备等级",
    "型号规格",
    "生产厂家",
    "安装位置及用途",
    "设备编号",
    "是否联锁",
    "备注",
    "工艺条件_介质名称",
    "工艺条件_设计温度",
    "工艺条件_阀前压力",
    "工艺条件_阀后压力",
    "阀体_公称通径",
    "阀体_连接方式及规格",
    "阀体_材质",
    "阀内件_阀座直径",
    "阀内件_阀芯材质",
    "阀内件_阀座材质",
    "阀内件_阀杆材质",
    "阀内件_流量特性",
    "阀内件_泄露等级",
    "阀内件_Cv值",
    "执行机构_形式",
    "执行机构_型号规格",
    "执行机构_厂家",
    "执行机构_作用形式",
    "执行机构_行程",
    "执行机构_弹簧范围",
    "执行机构_气源压力",
    "执行机构_故障位置",
    "执行机构_关阀时间",
    "执行机构_开阀时间",
]

FILTERABLE_FIELDS = [
    ("位号", "位号"),
    ("名称", "名称"),
    ("装置名称", "装置名称"),
    ("设备等级", "设备等级"),
    ("型号规格", "型号规格"),
    ("生产厂家", "生产厂家"),
    ("安装位置及用途", "安装位置及用途"),
    ("设备编号", "设备编号"),
    ("是否联锁", "是否联锁"),
    ("工艺条件_介质名称", "工艺条件_介质名称"),
    ("工艺条件_设计温度", "工艺条件_设计温度"),
    ("工艺条件_阀前压力", "工艺条件_阀前压力"),
    ("工艺条件_阀后压力", "工艺条件_阀后压力"),
    ("阀体_公称通径", "阀体_公称通径"),
    ("阀体_连接方式及规格", "阀体_连接方式及规格"),
    ("阀体_材质", "阀体_材质"),
    ("阀内件_阀座直径", "阀内件_阀座直径"),
    ("阀内件_阀芯材质", "阀内件_阀芯材质"),
    ("阀内件_阀座材质", "阀内件_阀座材质"),
    ("阀内件_阀杆材质", "阀内件_阀杆材质"),
    ("阀内件_流量特性", "阀内件_流量特性"),
    ("阀内件_泄露等级", "阀内件_泄露等级"),
    ("阀内件_Cv值", "阀内件_Cv值"),
    ("执行机构_形式", "执行机构_形式"),
    ("执行机构_型号规格", "执行机构_型号规格"),
    ("执行机构_厂家", "执行机构_厂家"),
    ("执行机构_作用形式", "执行机构_作用形式"),
    ("执行机构_行程", "执行机构_行程"),
    ("执行机构_弹簧范围", "执行机构_弹簧范围"),
    ("执行机构_气源压力", "执行机构_气源压力"),
    ("执行机构_故障位置", "执行机构_故障位置"),
    ("执行机构_关阀时间", "执行机构_关阀时间"),
    ("执行机构_开阀时间", "执行机构_开阀时间"),
]

IMPORT_COLUMN_MAP = {
    "装置名称": "装置名称",
    "位号": "位号",
    "名称": "名称",
    "设备等级": "设备等级",
    "型号规格": "型号规格",
    "生产厂家": "生产厂家",
    "安装位置及用途": "安装位置及用途",
    "工艺条件_介质名称": "工艺条件_介质名称",
    "工艺条件_设计温度": "工艺条件_设计温度",
    "工艺条件_阀前压力": "工艺条件_阀前压力",
    "工艺条件_阀后压力": "工艺条件_阀后压力",
    "阀体_公称通径": "阀体_公称通径",
    "阀体_连接方式及规格": "阀体_连接方式及规格",
    "阀体_材质": "阀体_材质",
    "阀内件_阀座直径": "阀内件_阀座直径",
    "阀内件_阀芯材质": "阀内件_阀芯材质",
    "阀内件_阀座材质": "阀内件_阀座材质",
    "阀内件_阀杆材质": "阀内件_阀杆材质",
    "阀内件_流量特性": "阀内件_流量特性",
    "阀内件_泄露等级": "阀内件_泄露等级",
    "阀内件_Cv值": "阀内件_Cv值",
    "执行机构_形式": "执行机构_形式",
    "执行机构_型号规格": "执行机构_型号规格",
    "执行机构_厂家": "执行机构_厂家",
    "执行机构_作用形式": "执行机构_作用形式",
    "执行机构_行程": "执行机构_行程",
    "执行机构_弹簧范围": "执行机构_弹簧范围",
    "执行机构_气源压力": "执行机构_气源压力",
    "执行机构_故障位置": "执行机构_故障位置",
    "执行机构_关阀时间": "执行机构_关阀时间",
    "执行机构_开阀时间": "执行机构_开阀时间",
    "设备编号": "设备编号",
    "是否联锁": "是否联锁",
    "备注": "备注",
}


def populate_valve_from_form(valve, form_data):
    """从表单数据填充台账对象"""
    for key in form_data:
        if key == "attachments":
            continue
        if hasattr(valve, key):
            setattr(valve, key, form_data.get(key))


def parse_attachments_data(attachments_json):
    """解析附件JSON数据"""
    if not attachments_json:
        return []
    try:
        return json.loads(attachments_json)
    except json.JSONDecodeError:
        return []


def create_attachment_from_data(valve_id, att_data):
    """从数据字典创建附件对象"""
    if not att_data.get("type"):
        return None
    return ValveAttachment(
        valve_id=valve_id,
        type=att_data.get("type"),
        名称=att_data.get("名称", ""),
        设备等级=att_data.get("设备等级", ""),
        型号规格=att_data.get("型号规格", ""),
        生产厂家=att_data.get("生产厂家", ""),
    )


def process_attachments_create(db, valve_id, attachments_json):
    """处理创建台账时的附件"""
    attachments = parse_attachments_data(attachments_json)
    for att in attachments:
        attachment = create_attachment_from_data(valve_id, att)
        if attachment:
            db.session.add(attachment)


def process_attachments_update(db, valve, attachments_json):
    """处理更新台账时的附件"""
    attachments = parse_attachments_data(attachments_json)
    if not attachments:
        return

    existing_ids = {att.id for att in valve.attachments}
    submitted_ids = set()

    for att in attachments:
        if not att.get("type"):
            continue
        att_id = att.get("id")
        if att_id:
            attachment = ValveAttachment.query.filter(
                ValveAttachment.id == att_id,
                ValveAttachment.valve_id == valve.id,
            ).first()
            if attachment:
                attachment.type = att.get("type")
                attachment.名称 = att.get("名称", "")
                attachment.设备等级 = att.get("设备等级", "")
                attachment.型号规格 = att.get("型号规格", "")
                attachment.生产厂家 = att.get("生产厂家", "")
                submitted_ids.add(att_id)
        else:
            attachment = create_attachment_from_data(valve.id, att)
            if attachment:
                db.session.add(attachment)

    for att_id in existing_ids - submitted_ids:
        attachment = ValveAttachment.query.filter(
            ValveAttachment.id == att_id,
            ValveAttachment.valve_id == valve.id,
        ).first()
        if attachment:
            db.session.delete(attachment)


def set_valve_status_after_submit(valve, user_id):
    """设置台账提交后的状态"""
    auto_approve = Setting.query.get("auto_approval")
    if auto_approve and auto_approve.value == "true":
        valve.status = "approved"
        valve.approved_by = user_id
        valve.approved_at = datetime.utcnow()
        if valve.ledger_id:
            ledger = Ledger.query.get(valve.ledger_id)
            if ledger:
                update_ledger_status(ledger)
        return "approve"
    else:
        valve.status = "pending"
        return "submit"


def get_valve_export_data(valve):
    """获取台账导出数据字典"""
    return {
        "装置名称": valve.装置名称,
        "位号": valve.位号,
        "名称": valve.名称,
        "设备等级": valve.设备等级,
        "型号规格": valve.型号规格,
        "生产厂家": valve.生产厂家,
        "安装位置及用途": valve.安装位置及用途,
        "工艺条件_介质名称": valve.工艺条件_介质名称,
        "工艺条件_设计温度": valve.工艺条件_设计温度,
        "工艺条件_阀前压力": valve.工艺条件_阀前压力,
        "工艺条件_阀后压力": valve.工艺条件_阀后压力,
        "阀体_公称通径": valve.阀体_公称通径,
        "阀体_连接方式及规格": valve.阀体_连接方式及规格,
        "阀体_材质": valve.阀体_材质,
        "阀内件_阀座直径": valve.阀内件_阀座直径,
        "阀内件_阀芯材质": valve.阀内件_阀芯材质,
        "阀内件_阀座材质": valve.阀内件_阀座材质,
        "阀内件_阀杆材质": valve.阀内件_阀杆材质,
        "阀内件_流量特性": valve.阀内件_流量特性,
        "阀内件_泄露等级": valve.阀内件_泄露等级,
        "阀内件_Cv值": valve.阀内件_Cv值,
        "执行机构_形式": valve.执行机构_形式,
        "执行机构_型号规格": valve.执行机构_型号规格,
        "执行机构_厂家": valve.执行机构_厂家,
        "执行机构_作用形式": valve.执行机构_作用形式,
        "执行机构_行程": valve.执行机构_行程,
        "执行机构_弹簧范围": valve.执行机构_弹簧范围,
        "执行机构_气源压力": valve.执行机构_气源压力,
        "执行机构_故障位置": valve.执行机构_故障位置,
        "执行机构_关阀时间": valve.执行机构_关阀时间,
        "执行机构_开阀时间": valve.执行机构_开阀时间,
        "设备编号": valve.设备编号,
        "是否联锁": valve.是否联锁,
        "备注": valve.备注,
    }
