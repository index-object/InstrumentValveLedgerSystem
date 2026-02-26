from flask import flash, redirect, url_for, request, render_template, make_response
from flask_login import login_required, current_user
from app.models import db, Valve
from app.routes.valves.permissions import require_leader
from app.routes.valves.forms import IMPORT_COLUMN_MAP, get_valve_export_data
from datetime import datetime
from io import BytesIO
import pandas as pd


def import_data():
    """导入数据路由"""
    if request.method == "POST":
        if "file" not in request.files:
            flash("请选择文件")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            flash("请选择文件")
            return redirect(request.url)

        if file:
            df = pd.read_excel(file)
            conflicts = []
            new_records = []

            for _, row in df.iterrows():
                if pd.isna(row.get("位号")):
                    continue

                existing = Valve.query.filter_by(位号=row["位号"]).first()
                if existing:
                    conflicts.append(
                        {
                            "位号": row["位号"],
                            "existing_id": existing.id,
                            "existing_name": existing.名称,
                            "new_data": row.to_dict(),
                        }
                    )
                else:
                    new_records.append(row.to_dict())

            from flask import session

            session["import_preview"] = {
                "conflicts": conflicts,
                "new_records": new_records,
                "filename": file.filename,
                "column_map": IMPORT_COLUMN_MAP,
            }

            return render_template(
                "valves/import_preview.html",
                conflicts=conflicts,
                new_records=new_records,
                total=len(conflicts) + len(new_records),
            )

    return render_template("valves/import.html")


def import_execute():
    """执行导入"""
    from flask import session
    from app.models import Setting, ApprovalLog

    conflict_mode = request.form.get("conflict_mode", "cancel")
    preview = session.get("import_preview")

    if not preview:
        flash("请先上传文件预览")
        return redirect(url_for("valves.import_data"))

    new_count = 0
    update_count = 0

    for record in preview["new_records"]:
        valve = Valve()
        for key, value in record.items():
            if hasattr(valve, key) and pd.notna(value):
                setattr(valve, key, str(value))

        valve.created_by = current_user.id

        auto_approve = Setting.query.get("auto_approval")
        if auto_approve and auto_approve.value == "true":
            valve.status = "approved"
            valve.approved_by = current_user.id
            valve.approved_at = datetime.utcnow()
        else:
            valve.status = "approved"

        db.session.add(valve)
        new_count += 1

    if conflict_mode == "overwrite":
        for conflict in preview["conflicts"]:
            existing = Valve.query.get(conflict["existing_id"])
            for key, value in conflict["new_data"].items():
                if hasattr(existing, key) and pd.notna(value):
                    setattr(existing, key, str(value))
            update_count += 1

    db.session.commit()
    session.pop("import_preview", None)

    flash(f"成功导入 {new_count} 条新记录，更新 {update_count} 条现有记录")
    return redirect(url_for("valves.list"))


def export_data():
    """导出数据"""
    ids = request.args.getlist("ids")
    if ids:
        valves = Valve.query.filter(Valve.id.in_(ids)).all()
    else:
        valves = Valve.query.filter_by(status="approved").all()

    data = [get_valve_export_data(v) for v in valves]
    df = pd.DataFrame(data)

    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    output = make_response(buffer.read())
    output.headers["Content-Disposition"] = "attachment; filename=valves.xlsx"
    output.headers["Content-Type"] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return output


def export_valve_pdf(id):
    """导出单个台账为PDF"""
    valve = Valve.query.get_or_404(id)

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
            f"attachment; filename=valve_{valve.位号}.pdf"
        )
        output.headers["Content-Type"] = "application/pdf"
        return output
    except ImportError:
        flash("PDF导出需要安装 WeasyPrint: pip install WeasyPrint")
        return redirect(url_for("valves.detail", id=id))


def register_export_routes(bp):
    """注册导出相关路由到蓝图"""
    bp.route("/import", methods=["GET", "POST"])(
        login_required(require_leader(import_data))
    )
    bp.route("/import/execute", methods=["POST"])(
        login_required(require_leader(import_execute))
    )
    bp.route("/export")(login_required(export_data))
    bp.route("/valve/<int:id>/export-pdf")(login_required(export_valve_pdf))
