from flask import flash, redirect, url_for, request, render_template, make_response, session, jsonify
from flask_login import login_required, current_user
from app.models import db, Valve, Setting, ValveAttachment
from app.routes.valves.permissions import require_employee_or_admin
from app.routes.valves.forms import get_valve_export_data
from app.routes.valves.import_processor import process_import_preview
from datetime import datetime
from io import BytesIO



def update_ledger_status(ledger):
    total = Valve.query.filter_by(ledger_id=ledger.id).count()
    if total == 0:
        return
    approved = Valve.query.filter_by(ledger_id=ledger.id, status="approved").count()
    if approved == total:
        ledger.status = "approved"
        ledger.approved_at = datetime.utcnow()


def import_data():
    """导入数据路由"""
    # 获取 ledger_id 参数
    ledger_id = request.args.get("ledger_id", type=int) or request.form.get("ledger_id", type=int)

    if request.method == "POST":
        if "file" not in request.files:
            if request.accept_mimetypes.accept_json:
                return jsonify({"error": "请选择文件"})
            flash("请选择文件")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            if request.accept_mimetypes.accept_json:
                return jsonify({"error": "请选择文件"})
            flash("请选择文件")
            return redirect(request.url)

        if file:
            # 获取现有阀门的位号映射
            existing_valves = {
                v.位号: v.id
                for v in Valve.query.filter(Valve.位号.isnot(None)).all()
            }

            # 使用新的导入处理器
            preview_data = process_import_preview(file, existing_valves)

            # AJAX 请求返回 JSON
            if request.accept_mimetypes.accept_json:
                # 如果有错误，返回详细错误信息
                if preview_data["errors"]:
                    return jsonify({
                        "error": "数据格式错误",
                        "errors": preview_data["errors"],
                        "warnings": preview_data["warnings"]
                    })

                # 构建预览数据
                preview_list = []
                for record in preview_data["new_records"]:
                    valve_data = record.get("valve_data", {})
                    preview_list.append({
                        "位号": valve_data.get("位号", ""),
                        "名称": valve_data.get("名称", ""),
                        "装置名称": valve_data.get("装置名称", ""),
                        "设备等级": valve_data.get("设备等级", ""),
                        "型号规格": valve_data.get("型号规格", ""),
                        "is_duplicate": False
                    })
                for conflict in preview_data["conflicts"]:
                    valve_data = conflict.get("valve_data", {})
                    preview_list.append({
                        "位号": conflict.get("位号", ""),
                        "名称": valve_data.get("名称", ""),
                        "装置名称": valve_data.get("装置名称", ""),
                        "设备等级": valve_data.get("设备等级", ""),
                        "型号规格": valve_data.get("型号规格", ""),
                        "is_duplicate": True
                    })

                # 保存预览数据到 session
                session["import_preview"] = {
                    "conflicts": preview_data["conflicts"],
                    "new_records": preview_data["new_records"],
                    "filename": file.filename,
                    "ledger_id": ledger_id,
                }

                return jsonify({
                    "preview": preview_list,
                    "total_count": preview_data["total"],
                    "duplicate_count": len(preview_data["conflicts"]),
                    "warnings": preview_data["warnings"]
                })

            # 传统表单提交返回 HTML
            for error in preview_data["errors"]:
                flash(error, "error")
            for warning in preview_data["warnings"]:
                flash(warning, "warning")

            session["import_preview"] = {
                "conflicts": preview_data["conflicts"],
                "new_records": preview_data["new_records"],
                "filename": file.filename,
                "ledger_id": ledger_id,
            }

            return render_template(
                "valves/import_preview.html",
                conflicts=preview_data["conflicts"],
                new_records=preview_data["new_records"],
                errors=preview_data["errors"],
                warnings=preview_data["warnings"],
                total=preview_data["total"],
            )

    return render_template("valves/import.html", ledger_id=ledger_id)


def import_execute():
    """执行导入"""
    conflict_mode = request.form.get("conflict_mode", "cancel")
    # 优先从表单获取 ledger_id，否则从 session 获取
    ledger_id = request.form.get("ledger_id", type=int)
    preview = session.get("import_preview")

    # AJAX 请求返回 JSON
    is_ajax = request.accept_mimetypes.accept_json

    if not preview:
        if is_ajax:
            return jsonify({"error": "请先上传文件预览"})
        flash("请先上传文件预览")
        return redirect(url_for("valves.import_data"))

    # 使用表单或 session 中的 ledger_id
    if not ledger_id:
        ledger_id = preview.get("ledger_id")

    new_count = 0
    update_count = 0
    attachment_count = 0
    errors = []

    try:
        # 处理新记录
        for record in preview["new_records"]:
            valve_data = record.get("valve_data", {})
            attachments = record.get("attachments", [])

            valve = Valve()
            for key, value in valve_data.items():
                if hasattr(valve, key) and value is not None:
                    setattr(valve, key, value)

            valve.created_by = current_user.id

            # 关联 ledger_id
            if ledger_id:
                valve.ledger_id = ledger_id

            # 设置审批状态 - 默认为草稿
            auto_approve = Setting.query.get("auto_approval")
            if auto_approve and auto_approve.value == "true":
                valve.status = "approved"
                valve.approved_by = current_user.id
                valve.approved_at = datetime.utcnow()
            else:
                valve.status = "draft"

            db.session.add(valve)
            db.session.flush()  # 获取 valve.id

            # 创建附件
            for att_data in attachments:
                attachment = ValveAttachment(
                    valve_id=valve.id,
                    名称=att_data.get("名称"),
                    type=att_data.get("type"),
                    型号规格=att_data.get("型号规格"),
                    生产厂家=att_data.get("生产厂家"),
                    设备等级=att_data.get("设备等级"),
                )
                db.session.add(attachment)
                attachment_count += 1

            new_count += 1

        # 处理冲突记录（覆盖模式）
        if conflict_mode == "overwrite":
            for conflict in preview["conflicts"]:
                existing = Valve.query.get(conflict["existing_id"])
                if existing:
                    valve_data = conflict.get("valve_data", {})
                    for key, value in valve_data.items():
                        if hasattr(existing, key) and value is not None:
                            setattr(existing, key, value)
                    # 更新 ledger_id
                    if ledger_id:
                        existing.ledger_id = ledger_id
                    update_count += 1

        db.session.commit()
        session.pop("import_preview", None)

        message = f"成功导入 {new_count} 条新记录"
        if update_count > 0:
            message += f"，更新 {update_count} 条现有记录"
        if attachment_count > 0:
            message += f"，创建 {attachment_count} 个附件"

        if is_ajax:
            return jsonify({"success": True, "message": message, "ledger_id": ledger_id})

        flash(message)
        if ledger_id:
            return redirect(url_for("ledgers.detail", id=ledger_id))
        return redirect(url_for("valves.list"))

    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        errors.append(error_msg)

        if is_ajax:
            return jsonify({
                "error": "导入过程中发生错误",
                "errors": errors
            })

        flash(f"导入失败: {error_msg}")
        return redirect(url_for("valves.import_data"))


def export_data():
    """导出数据"""
    ids = request.args.getlist("ids")
    if ids:
        valves = Valve.query.filter(Valve.id.in_(ids)).all()
    else:
        valves = Valve.query.filter_by(status="approved").all()

    data = [get_valve_export_data(v) for v in valves]
    import pandas as pd
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
        login_required(require_employee_or_admin(import_data))
    )
    bp.route("/import/execute", methods=["POST"])(
        login_required(require_employee_or_admin(import_execute))
    )
    bp.route("/export")(login_required(export_data))
    bp.route("/valve/<int:id>/export-pdf")(login_required(export_valve_pdf))
