from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    send_from_directory,
    make_response,
    session,
)
from flask_login import login_required, current_user
from app.models import db, Valve, Setting, ApprovalLog, User, ValveAttachment
from werkzeug.utils import secure_filename
from datetime import datetime
import os

valves = Blueprint("valves", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@valves.route("/valves")
@login_required
def list():
    query = Valve.query

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    search = request.args.get("search")
    if search:
        query = query.filter(
            (Valve.位号.contains(search))
            | (Valve.名称.contains(search))
            | (Valve.装置名称.contains(search))
            | (Valve.设备编号.contains(search))
        )

    status = request.args.get("status")
    if status:
        query = query.filter(Valve.status == status)

    装置名称 = request.args.get("装置名称")
    if 装置名称:
        query = query.filter(Valve.装置名称 == 装置名称)

    filter_type = request.args.get("filter")
    if filter_type == "mine":
        query = query.filter(Valve.created_by == current_user.id)

    装置列表 = (
        db.session.query(Valve.装置名称)
        .distinct()
        .filter(Valve.装置名称.isnot(None))
        .all()
    )
    装置列表 = [r[0] for r in 装置列表 if r[0]]

    pagination = query.order_by(Valve.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    valves_list = pagination.items

    return render_template(
        "valves/list.html", valves=valves_list, pagination=pagination, 装置列表=装置列表
    )


@valves.route("/valve/<int:id>")
@login_required
def detail(id):
    valve = Valve.query.get_or_404(id)
    return render_template("valves/detail.html", valve=valve)


@valves.route("/valve/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        valve = Valve()
        for key in request.form:
            if hasattr(valve, key):
                setattr(valve, key, request.form.get(key))

        valve.created_by = current_user.id
        valve.status = "draft"

        db.session.add(valve)
        db.session.commit()

        log = ApprovalLog(valve_id=valve.id, action="submit", user_id=current_user.id)
        db.session.add(log)

        auto_approve = Setting.query.get("auto_approval")
        if auto_approve and auto_approve.value == "true":
            valve.status = "approved"
            valve.approved_by = current_user.id
            valve.approved_at = datetime.utcnow()
            log.action = "approve"
        else:
            valve.status = "pending"

        db.session.commit()
        flash("提交成功")
        return redirect(url_for("valves.list"))

    return render_template("valves/form.html", valve=None)


@valves.route("/valve/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit(id):
    valve = Valve.query.get_or_404(id)

    can_edit = valve.created_by == current_user.id or current_user.role in [
        "leader",
        "admin",
    ]
    if not can_edit:
        flash("无权编辑")
        return redirect(url_for("valves.detail", id=id))

    if valve.status not in ["draft", "rejected", "approved"]:
        flash("当前状态无法编辑")
        return redirect(url_for("valves.detail", id=id))

    if request.method == "POST":
        for key in request.form:
            if hasattr(valve, key):
                setattr(valve, key, request.form.get(key))

        valve.status = "draft"
        db.session.commit()

        log = ApprovalLog(valve_id=valve.id, action="submit", user_id=current_user.id)
        db.session.add(log)

        auto_approve = Setting.query.get("auto_approval")
        if auto_approve and auto_approve.value == "true":
            valve.status = "approved"
            valve.approved_by = current_user.id
            valve.approved_at = datetime.utcnow()
            log.action = "approve"
        else:
            valve.status = "pending"

        db.session.commit()
        flash("提交成功")
        return redirect(url_for("valves.list"))

    return render_template("valves/form.html", valve=valve)


@valves.route("/valve/delete/<int:id>", methods=["POST"])
@login_required
def delete(id):
    valve = Valve.query.get_or_404(id)

    can_delete = valve.created_by == current_user.id or current_user.role in [
        "leader",
        "admin",
    ]
    if not can_delete:
        flash("无权删除")
        return redirect(url_for("valves.detail", id=id))

    if valve.status not in ["draft", "rejected"]:
        flash("当前状态无法删除")
        return redirect(url_for("valves.detail", id=id))

    db.session.delete(valve)
    db.session.commit()
    flash("删除成功")
    return redirect(url_for("valves.list"))


@valves.route("/valves/batch-delete", methods=["POST"])
@login_required
def batch_delete():
    ids = request.form.getlist("ids")
    if not ids:
        flash("请选择要删除的记录")
        return redirect(url_for("valves.list"))

    count = 0
    for id in ids:
        valve = Valve.query.get(int(id))
        if valve and valve.status in ["draft", "rejected"]:
            can_delete = valve.created_by == current_user.id or current_user.role in [
                "leader",
                "admin",
            ]
            if can_delete:
                db.session.delete(valve)
                count += 1

    db.session.commit()
    flash(f"成功删除 {count} 条记录")
    return redirect(url_for("valves.list"))


@valves.route("/valves/batch-approve", methods=["POST"])
@login_required
def batch_approve():
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(url_for("valves.list"))

    ids = request.form.getlist("ids")
    if not ids:
        flash("请选择要审批的记录")
        return redirect(url_for("valves.approvals"))

    count = 0
    for id in ids:
        valve = Valve.query.get(int(id))
        if valve and valve.status == "pending":
            valve.status = "approved"
            valve.approved_by = current_user.id
            valve.approved_at = datetime.utcnow()

            log = ApprovalLog(
                valve_id=valve.id,
                action="approve",
                user_id=current_user.id,
                comment=request.form.get("comment", ""),
            )
            db.session.add(log)
            count += 1

    db.session.commit()
    flash(f"成功审批 {count} 条记录")
    return redirect(url_for("valves.approvals"))


@valves.route("/valves/batch-reject", methods=["POST"])
@login_required
def batch_reject():
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(url_for("valves.list"))

    ids = request.form.getlist("ids")
    if not ids:
        flash("请选择要驳回的记录")
        return redirect(url_for("valves.approvals"))

    comment = request.form.get("comment", "")
    count = 0
    for id in ids:
        valve = Valve.query.get(int(id))
        if valve and valve.status == "pending":
            valve.status = "rejected"

            log = ApprovalLog(
                valve_id=valve.id,
                action="reject",
                user_id=current_user.id,
                comment=comment,
            )
            db.session.add(log)
            count += 1

    db.session.commit()
    flash(f"成功驳回 {count} 条记录")
    return redirect(url_for("valves.approvals"))


@valves.route("/my-applications")
@login_required
def my_applications():
    my_valves = (
        Valve.query.filter_by(created_by=current_user.id)
        .order_by(Valve.created_at.desc())
        .all()
    )
    return render_template("valves/my_applications.html", valves=my_valves)


@valves.route("/approvals")
@login_required
def approvals():
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(url_for("valves.list"))

    status = request.args.get("status", "pending")
    if status == "pending":
        valves_list = Valve.query.filter_by(status="pending").all()
    elif status == "approved":
        valves_list = Valve.query.filter_by(status="approved").all()
    else:
        valves_list = Valve.query.filter_by(status="rejected").all()

    return render_template(
        "valves/approvals.html", valves=valves_list, current_status=status
    )


@valves.route("/valve/approve/<int:id>", methods=["POST"])
@login_required
def approve(id):
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(url_for("valves.list"))

    valve = Valve.query.get_or_404(id)
    valve.status = "approved"
    valve.approved_by = current_user.id
    valve.approved_at = datetime.utcnow()

    log = ApprovalLog(
        valve_id=valve.id,
        action="approve",
        user_id=current_user.id,
        comment=request.form.get("comment", ""),
    )
    db.session.add(log)
    db.session.commit()

    flash("审批通过")
    return redirect(url_for("valves.approvals"))


@valves.route("/valve/reject/<int:id>", methods=["POST"])
@login_required
def reject(id):
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(url_for("valves.list"))

    valve = Valve.query.get_or_404(id)
    valve.status = "rejected"

    log = ApprovalLog(
        valve_id=valve.id,
        action="reject",
        user_id=current_user.id,
        comment=request.form.get("comment", ""),
    )
    db.session.add(log)
    db.session.commit()

    flash("已驳回")
    return redirect(url_for("valves.approvals"))


@valves.route("/import", methods=["GET", "POST"])
@login_required
def import_data():
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(url_for("valves.list"))

    if request.method == "POST":
        if "file" not in request.files:
            flash("请选择文件")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            flash("请选择文件")
            return redirect(request.url)

        if file:
            import pandas as pd

            df = pd.read_excel(file)

            column_map = {
                "序号": "序号",
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

            new_count = 0
            update_count = 0
            for _, row in df.iterrows():
                if pd.isna(row.get("位号")):
                    continue

                existing = Valve.query.filter_by(位号=row["位号"]).first()
                if existing:
                    for excel_col, db_col in column_map.items():
                        if excel_col in df.columns and pd.notna(row.get(excel_col)):
                            setattr(existing, db_col, str(row[excel_col]))
                    update_count += 1
                else:
                    valve = Valve()
                    for excel_col, db_col in column_map.items():
                        if excel_col in df.columns and pd.notna(row.get(excel_col)):
                            setattr(valve, db_col, str(row[excel_col]))

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

            db.session.commit()
            flash(f"成功导入 {new_count} 条新记录，更新 {update_count} 条现有记录")
            return redirect(url_for("valves.list"))

    return render_template("valves/import.html")


@valves.route("/export")
@login_required
def export_data():
    import pandas as pd

    ids = request.args.getlist("ids")
    if ids:
        valves = Valve.query.filter(Valve.id.in_(ids)).all()
    else:
        valves = Valve.query.filter_by(status="approved").all()

    data = []
    for v in valves:
        data.append(
            {
                "序号": v.序号,
                "装置名称": v.装置名称,
                "位号": v.位号,
                "名称": v.名称,
                "设备等级": v.设备等级,
                "型号规格": v.型号规格,
                "生产厂家": v.生产厂家,
                "安装位置及用途": v.安装位置及用途,
                "工艺条件_介质名称": v.工艺条件_介质名称,
                "工艺条件_设计温度": v.工艺条件_设计温度,
                "工艺条件_阀前压力": v.工艺条件_阀前压力,
                "工艺条件_阀后压力": v.工艺条件_阀后压力,
                "阀体_公称通径": v.阀体_公称通径,
                "阀体_连接方式及规格": v.阀体_连接方式及规格,
                "阀体_材质": v.阀体_材质,
                "阀内件_阀座直径": v.阀内件_阀座直径,
                "阀内件_阀芯材质": v.阀内件_阀芯材质,
                "阀内件_阀座材质": v.阀内件_阀座材质,
                "阀内件_阀杆材质": v.阀内件_阀杆材质,
                "阀内件_流量特性": v.阀内件_流量特性,
                "阀内件_泄露等级": v.阀内件_泄露等级,
                "阀内件_Cv值": v.阀内件_Cv值,
                "执行机构_形式": v.执行机构_形式,
                "执行机构_型号规格": v.执行机构_型号规格,
                "执行机构_厂家": v.执行机构_厂家,
                "执行机构_作用形式": v.执行机构_作用形式,
                "执行机构_行程": v.执行机构_行程,
                "执行机构_弹簧范围": v.执行机构_弹簧范围,
                "执行机构_气源压力": v.执行机构_气源压力,
                "执行机构_故障位置": v.执行机构_故障位置,
                "执行机构_关阀时间": v.执行机构_关阀时间,
                "执行机构_开阀时间": v.执行机构_开阀时间,
                "设备编号": v.设备编号,
                "是否联锁": v.是否联锁,
                "备注": v.备注,
            }
        )

    df = pd.DataFrame(data)
    from io import BytesIO

    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    output = make_response(buffer.read())
    output.headers["Content-Disposition"] = "attachment; filename=valves.xlsx"
    output.headers["Content-Type"] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    return output


@valves.route("/valve/<int:id>/photos", methods=["GET", "POST"])
@login_required
def photos(id):
    from app.models import ValvePhoto

    valve = Valve.query.get_or_404(id)

    if request.method == "POST":
        if "photo" not in request.files:
            flash("请选择文件")
            return redirect(request.url)

        file = request.files["photo"]
        if file and allowed_file(file.filename):
            from flask import current_app

            filename = secure_filename(
                f"{valve.位号}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
            )
            file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))

            photo = ValvePhoto(
                valve_id=valve.id,
                filename=filename,
                description=request.form.get("description", ""),
                uploaded_by=current_user.id,
            )
            db.session.add(photo)
            db.session.commit()
            flash("上传成功")

    return render_template("valves/photos.html", valve=valve)


@valves.route("/valve/<int:id>/maintenance", methods=["GET", "POST"])
@login_required
def maintenance(id):
    from app.models import MaintenanceRecord

    valve = Valve.query.get_or_404(id)

    if request.method == "POST":
        检修时间_str = request.form.get("检修时间")
        检修时间 = None
        if 检修时间_str:
            try:
                检修时间 = datetime.strptime(检修时间_str, "%Y-%m-%dT%H:%M")
            except:
                try:
                    检修时间 = datetime.strptime(检修时间_str, "%Y-%m-%d %H:%M:%S")
                except:
                    pass

        record = MaintenanceRecord(
            valve_id=valve.id,
            所属中心=request.form.get("所属中心"),
            设备位号=request.form.get("设备位号"),
            设备名称=request.form.get("设备名称"),
            检修时间=检修时间,
            检修内容=request.form.get("检修内容"),
            检修人员=request.form.get("检修人员"),
            类型=request.form.get("类型"),
            created_by=current_user.id,
        )
        db.session.add(record)
        db.session.commit()
        flash("添加成功")
        return redirect(url_for("valves.maintenance", id=id))

    records = (
        MaintenanceRecord.query.filter_by(valve_id=id)
        .order_by(MaintenanceRecord.检修时间.desc())
        .all()
    )
    return render_template("valves/maintenance.html", valve=valve, records=records)


@valves.route("/maintenance")
@login_required
def maintenance_list():
    from app.models import MaintenanceRecord

    query = MaintenanceRecord.query

    search = request.args.get("search")
    if search:
        query = query.filter(MaintenanceRecord.检修内容.contains(search))

    valve_id = request.args.get("valve_id")
    if valve_id:
        query = query.filter(MaintenanceRecord.valve_id == int(valve_id))

    records = query.order_by(MaintenanceRecord.检修时间.desc()).all()
    return render_template("maintenance/list.html", records=records)


@valves.route("/valve/<int:id>/attachments", methods=["GET", "POST"])
@login_required
def attachments(id):
    valve = Valve.query.get_or_404(id)

    if request.method == "POST":
        attachment = ValveAttachment(
            valve_id=valve.id,
            名称=request.form.get("名称"),
            设备等级=request.form.get("设备等级"),
            型号规格=request.form.get("型号规格"),
            生产厂家=request.form.get("生产厂家"),
            type=request.form.get("type"),
        )
        db.session.add(attachment)
        db.session.commit()
        flash("附件添加成功")
        return redirect(url_for("valves.attachments", id=id))

    attachments_list = valve.attachments
    return render_template(
        "valves/attachments.html", valve=valve, attachments=attachments_list
    )


@valves.route("/valve/<int:valve_id>/attachment/<int:att_id>/delete", methods=["POST"])
@login_required
def delete_attachment(valve_id, att_id):
    attachment = ValveAttachment.query.get_or_404(att_id)
    if attachment.valve_id != valve_id:
        flash("附件不存在")
        return redirect(url_for("valves.detail", id=valve_id))

    can_edit = attachment.valve.created_by == current_user.id or current_user.role in [
        "leader",
        "admin",
    ]
    if not can_edit:
        flash("无权删除")
        return redirect(url_for("valves.detail", id=valve_id))

    db.session.delete(attachment)
    db.session.commit()
    flash("附件删除成功")
    return redirect(url_for("valves.detail", id=valve_id))
