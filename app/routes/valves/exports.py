# coding=utf-8
"""阀门台账导出。

导出的数据范围必须与用户在列表页上看到的一致：既受角色、来源上下文
（全部台账 / 我的台账 / 审批中心 / 数据统计）约束，也受当前搜索、状态
与列筛选约束；勾选导出（ids）同样不能绕过这些口径。
"""

from urllib.parse import quote

from flask import (
    abort,
    flash,
    redirect,
    url_for,
    request,
    make_response,
)
from flask_login import login_required

from app.models import Ledger
from app.devices import DeviceTypeRegistry
from app.devices.valve_helper import (
    get_valve_by_id,
    get_all_valve_models,
    is_valve_type,
)
from app.routes.valves.forms import get_valve_export_data
from app.routes.valves.permissions import (
    can_export_data,
    can_export_device,
)
from app.utils.excel_export import (
    STATUS_LABELS,
    build_excel_response,
    exporter_label,
    user_labels,
)
from app.utils.export_scope import (
    apply_ledger_scope,
    apply_search,
    apply_field_filters,
)
from app.utils.navigation import get_from_param, url_with_params
from datetime import datetime
from io import BytesIO


def export_data():
    """导出阀门台账数据（范围与用户当前可见的列表一致）。"""
    if not can_export_data():
        flash("无权导出数据")
        return redirect(url_for("ledgers.list"))

    device_type = request.args.get("device_type")
    from_param = get_from_param()
    ledger_id = request.args.get("ledger_id", type=int)
    ids = request.args.getlist("ids")

    ledger = None
    if ledger_id:
        ledger = Ledger.query.get(ledger_id)
        if not ledger:
            abort(404)

    # 非阀门类型统一交给设备导出处理，避免用阀门字段取数导致 500
    if device_type and not is_valve_type(device_type):
        return redirect(url_with_params("devices.export", type_code=device_type))

    config = DeviceTypeRegistry.get(device_type) if device_type else None
    if config and config.model_class:
        models = [config.model_class]
    else:
        models = get_all_valve_models()

    records = []
    for model in models:
        query = model.query
        query = apply_ledger_scope(query, model, ledger, from_param, request.args)
        query = apply_search(query, model, request.args, broad=True)
        query = apply_field_filters(query, model, request.args)
        if ids:
            query = query.filter(model.id.in_(ids))
        records.extend(query.all())

    # 逐条按导出权限收口：勾选导出也不能拿到他人的草稿 / 待审批数据
    records = [r for r in records if can_export_device(r)]
    records.sort(key=lambda r: r.id or 0)

    names = user_labels({r.created_by for r in records})
    ledger_name = ledger.名称 if ledger is not None else ""

    data = []
    for record in records:
        row = {
            "台账合集": ledger_name,
            "状态": STATUS_LABELS.get(record.status, record.status or ""),
            "创建人": names.get(record.created_by, ""),
        }
        row.update(get_valve_export_data(record))
        data.append(row)

    import pandas as pd

    df = pd.DataFrame(data)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"阀门台账_{ledger_name or exporter_label()}_{stamp}"
    return build_excel_response(df, filename)


def export_valve_pdf(id):
    """导出单个台账为PDF"""
    valve = get_valve_by_id(id)
    if not valve:
        flash("未找到该阀门")
        return redirect(url_for("valves.list"))

    if not can_export_device(valve):
        flash("无权导出该台账")
        return redirect(url_for("valves.list"))

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>台账详情 - {valve.位号}</title>
        <style>
            body {{ font-family: SimSun, serif; padding: 20px; }}
            h1 {{ text-align: center; color: #333; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f5f5f5; }}
            .section {{ margin: 20px 0; }}
            .section-title {{ background-color: #4a90d9; color: white; padding: 10px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>仪表阀门台账</h1>
        
        <div class="section">
            <div class="section-title">基本信息</div>
            <table>
                <tr><th>位号</th><td>{valve.位号 or ""}</td><th>名称</th><td>{valve.名称 or ""}</td></tr>
                <tr><th>装置名称</th><td>{valve.装置名称 or ""}</td><th>设备等级</th><td>{valve.设备等级 or ""}</td></tr>
                <tr><th>型号规格</th><td>{valve.型号规格 or ""}</td><th>生产厂家</th><td>{valve.生产厂家 or ""}</td></tr>
                <tr><th>安装位置</th><td colspan="3">{valve.安装位置及用途 or ""}</td></tr>
                <tr><th>设备编号</th><td>{valve.设备编号 or ""}</td><th>是否联锁</th><td>{valve.是否联锁 or ""}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <div class="section-title">工艺条件</div>
            <table>
                <tr><th>介质名称</th><td>{valve.工艺条件_介质名称 or ""}</td><th>设计温度</th><td>{valve.工艺条件_设计温度 or ""}</td></tr>
                <tr><th>阀前压力</th><td>{valve.工艺条件_阀前压力 or ""}</td><th>阀后压力</th><td>{valve.工艺条件_阀后压力 or ""}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <div class="section-title">阀体信息</div>
            <table>
                <tr><th>公称通径</th><td>{valve.阀体_公称通径 or ""}</td><th>连接方式</th><td>{valve.阀体_连接方式及规格 or ""}</td></tr>
                <tr><th>阀体材质</th><td colspan="3">{valve.阀体_材质 or ""}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <div class="section-title">阀内件信息</div>
            <table>
                <tr><th>阀座直径</th><td>{valve.阀内件_阀座直径 or ""}</td><th>阀芯材质</th><td>{valve.阀内件_阀芯材质 or ""}</td></tr>
                <tr><th>阀座材质</th><td>{valve.阀内件_阀座材质 or ""}</td><th>阀杆材质</th><td>{valve.阀内件_阀杆材质 or ""}</td></tr>
                <tr><th>流量特性</th><td>{valve.阀内件_流量特性 or ""}</td><th>泄露等级</th><td>{valve.阀内件_泄露等级 or ""}</td></tr>
                <tr><th>Cv值</th><td colspan="3">{valve.阀内件_Cv值 or ""}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <div class="section-title">执行机构信息</div>
            <table>
                <tr><th>形式</th><td>{valve.执行机构_形式 or ""}</td><th>型号规格</th><td>{valve.执行机构_型号规格 or ""}</td></tr>
                <tr><th>厂家</th><td>{valve.执行机构_厂家 or ""}</td><th>作用形式</th><td>{valve.执行机构_作用形式 or ""}</td></tr>
                <tr><th>行程</th><td>{valve.执行机构_行程 or ""}</td><th>弹簧范围</th><td>{valve.执行机构_弹簧范围 or ""}</td></tr>
                <tr><th>气源压力</th><td>{valve.执行机构_气源压力 or ""}</td><th>故障位置</th><td>{valve.执行机构_故障位置 or ""}</td></tr>
                <tr><th>关阀时间</th><td>{valve.执行机构_关阀时间 or ""}</td><th>开阀时间</th><td>{valve.执行机构_开阀时间 or ""}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <div class="section-title">备注</div>
            <p>{valve.备注 or "无"}</p>
        </div>
        
        <p style="text-align: right; color: #666; margin-top: 30px;">
            导出时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </p>
    </body>
    </html>
    """

    try:
        from weasyprint import HTML

        pdf_buffer = BytesIO()
        HTML(string=html).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        output = make_response(pdf_buffer.read())
        output.headers["Content-Disposition"] = (
            f"attachment; filename=valve_{quote(valve.位号 or str(valve.id))}.pdf"
        )
        output.headers["Content-Type"] = "application/pdf"
        return output
    except ImportError:
        flash("PDF导出需要安装 WeasyPrint: pip install WeasyPrint")
        return redirect(url_for("valves.detail", id=id))


def register_export_routes(bp):
    """注册导出相关路由到蓝图"""
    # 导入功能已迁移到 /imports 统一界面
    bp.route("/export")(login_required(export_data))
    bp.route("/valve/<int:id>/export-pdf")(login_required(export_valve_pdf))
