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
    jsonify,
)
from flask_login import login_required, current_user
from app.models import db, Valve, Setting, ApprovalLog, User, ValveAttachment
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
from datetime import datetime
import os

valves = Blueprint("valves", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@valves.route("/valve/check-tag")
@login_required
def check_tag():
    tag = request.args.get("位号")
    if not tag:
        return jsonify({"valid": True})

    exclude_id = request.args.get("exclude_id", type=int)

    query = Valve.query.filter(Valve.位号 == tag, Valve.status != "draft")
    if exclude_id:
        query = query.filter(Valve.id != exclude_id)

    exists = query.first() is not None

    if exists:
        return jsonify({"valid": False, "message": "位号已存在"})
    return jsonify({"valid": True})


@valves.route("/valves")
@login_required
def list():
    query = Valve.query

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    search = request.args.get("search")
    if search:
        search_conditions = []
        for column in Valve.__table__.columns:
            if column.name not in [
                "id",
                "created_by",
                "approved_by",
                "approved_at",
                "created_at",
                "updated_at",
                "status",
            ]:
                col = getattr(Valve, column.name)
                search_conditions.append(col.contains(search))
        if search_conditions:
            query = query.filter(or_(*search_conditions))

    status = request.args.get("status")
    if status:
        query = query.filter(Valve.status == status)

    装置名称 = request.args.get("装置名称")
    if 装置名称:
        query = query.filter(Valve.装置名称 == 装置名称)

    filter_type = request.args.get("filter")
    if filter_type == "mine":
        query = query.filter(Valve.created_by == current_user.id)

    if filter_type == "mine":
        query = query.filter(Valve.created_by == current_user.id)

    filterable_fields = [
        ("序号", "序号"),
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

    filter_options = {}
    for label, field in filterable_fields:
        if hasattr(Valve, field):
            values = (
                db.session.query(getattr(Valve, field))
                .distinct()
                .filter(getattr(Valve, field).isnot(None), getattr(Valve, field) != "")
                .all()
            )
            filter_options[field] = sorted([v[0] for v in values if v[0]], key=str)

    active_filters = {}
    for label, field in filterable_fields:
        values = request.args.getlist(field)
        if values and hasattr(Valve, field):
            field_filter = getattr(Valve, field).in_(values)
            query = query.filter(field_filter)
            active_filters[field] = values

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
        "valves/list.html",
        valves=valves_list,
        pagination=pagination,
        装置列表=装置列表,
        active_filters=active_filters,
        filter_options=filter_options,
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
        位号 = request.form.get("位号")
        if 位号:
            existing = Valve.query.filter(
                Valve.位号 == 位号, Valve.status != "draft"
            ).first()
            if existing:
                flash("位号已存在，请使用其他位号")
                return redirect(url_for("valves.new"))

        valve = Valve()
        for key in request.form:
            if key == "attachments":
                continue
            if hasattr(valve, key):
                setattr(valve, key, request.form.get(key))

        valve.created_by = current_user.id
        valve.status = "draft"

        try:
            db.session.add(valve)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            draft = Valve.query.filter(
                Valve.位号 == 位号,
                Valve.status == "draft",
                Valve.created_by == current_user.id,
            ).first()
            if draft:
                db.session.delete(draft)
                db.session.commit()
                try:
                    db.session.add(valve)
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    flash("位号已存在，请使用其他位号")
                    return redirect(url_for("valves.new"))
            else:
                flash("位号已存在，请使用其他位号")
                return redirect(url_for("valves.new"))

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

        # 处理附件数据
        attachments_data = request.form.get("attachments")
        if attachments_data:
            import json

            try:
                attachments = json.loads(attachments_data)
                for att in attachments:
                    if att.get("type"):
                        attachment = ValveAttachment(
                            valve_id=valve.id,
                            type=att.get("type"),
                            名称=att.get("名称", ""),
                            设备等级=att.get("设备等级", ""),
                            型号规格=att.get("型号规格", ""),
                            生产厂家=att.get("生产厂家", ""),
                        )
                        db.session.add(attachment)
                db.session.commit()
            except json.JSONDecodeError:
                db.session.rollback()

        flash("提交成功")
        return redirect(url_for("valves.list"))

    return render_template("valves/form.html", valve=None)


@valves.route("/valve/draft/save", methods=["POST"])
@login_required
def save_draft():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "无效数据"})

    valve_id = data.get("valve_id")

    if valve_id:
        valve = Valve.query.get(valve_id)
        if not valve:
            return jsonify({"success": False, "message": "台账不存在"})

        can_edit = valve.created_by == current_user.id or current_user.role in [
            "leader",
            "admin",
        ]
        if not can_edit:
            return jsonify({"success": False, "message": "无权编辑"})
    else:
        valve = Valve()
        valve.created_by = current_user.id
        valve.status = "draft"
        db.session.add(valve)

    for key, value in data.get("formData", {}).items():
        if hasattr(valve, key):
            setattr(valve, key, value)

    db.session.commit()

    return jsonify({"success": True, "valve_id": valve.id})


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
        位号 = request.form.get("位号")
        if 位号:
            existing = Valve.query.filter(Valve.位号 == 位号, Valve.id != id).first()
            if existing:
                flash("位号已存在，请使用其他位号")
                return redirect(url_for("valves.edit", id=id))

        for key in request.form:
            if key == "attachments":
                continue
            if hasattr(valve, key):
                setattr(valve, key, request.form.get(key))

        valve.status = "draft"

        # 处理附件数据
        attachments_data = request.form.get("attachments")
        if attachments_data:
            import json

            try:
                attachments = json.loads(attachments_data)

                existing_ids = {att.id for att in valve.attachments}
                submitted_ids = set()

                for att in attachments:
                    if att.get("type"):
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
                            attachment = ValveAttachment(
                                valve_id=valve.id,
                                type=att.get("type"),
                                名称=att.get("名称", ""),
                                设备等级=att.get("设备等级", ""),
                                型号规格=att.get("型号规格", ""),
                                生产厂家=att.get("生产厂家", ""),
                            )
                            db.session.add(attachment)

                # 只有有编辑权限的用户才能删除附件
                if can_edit:
                    for att_id in existing_ids - submitted_ids:
                        attachment = ValveAttachment.query.filter(
                            ValveAttachment.id == att_id,
                            ValveAttachment.valve_id == valve.id,
                        ).first()
                        if attachment:
                            db.session.delete(attachment)
            except json.JSONDecodeError:
                pass

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

            session["import_preview"] = {
                "conflicts": conflicts,
                "new_records": new_records,
                "filename": file.filename,
                "column_map": column_map,
            }

            return render_template(
                "valves/import_preview.html",
                conflicts=conflicts,
                new_records=new_records,
                total=len(conflicts) + len(new_records),
            )

    return render_template("valves/import.html")


@valves.route("/import/execute", methods=["POST"])
@login_required
def import_execute():
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(url_for("valves.list"))

    import pandas as pd

    conflict_mode = request.form.get("conflict_mode", "cancel")

    preview = session.get("import_preview")
    if not preview:
        flash("请先上传文件预览")
        return redirect(url_for("valves.import_data"))

    column_map = preview.get("column_map", {})
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
    elif conflict_mode == "skip":
        pass

    db.session.commit()
    session.pop("import_preview", None)

    flash(f"成功导入 {new_count} 条新记录，更新 {update_count} 条现有记录")
    return redirect(url_for("valves.list"))


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


@valves.route("/valve/<int:id>/export-pdf")
@login_required
def export_valve_pdf(id):
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

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    pagination = query.order_by(MaintenanceRecord.检修时间.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template(
        "maintenance/list.html", records=pagination.items, pagination=pagination
    )


@valves.route("/maintenance/batch-delete", methods=["POST"])
@login_required
def maintenance_batch_delete():
    from app.models import MaintenanceRecord

    ids = request.form.getlist("ids")
    if not ids:
        flash("请选择要删除的记录")
        return redirect(url_for("valves.maintenance_list"))

    count = MaintenanceRecord.query.filter(MaintenanceRecord.id.in_(ids)).delete(
        synchronize_session=False
    )
    db.session.commit()
    flash(f"成功删除 {count} 条记录")
    return redirect(url_for("valves.maintenance_list"))


@valves.route("/maintenance/export")
@login_required
def maintenance_export():
    from app.models import MaintenanceRecord
    import pandas as pd

    ids = request.args.getlist("ids")
    if ids:
        records = MaintenanceRecord.query.filter(MaintenanceRecord.id.in_(ids)).all()
    else:
        records = MaintenanceRecord.query.order_by(
            MaintenanceRecord.检修时间.desc()
        ).all()

    data = []
    for r in records:
        data.append(
            {
                "设备位号": r.设备位号,
                "设备名称": r.设备名称,
                "所属中心": r.所属中心,
                "检修时间": r.检修时间.strftime("%Y-%m-%d %H:%M") if r.检修时间 else "",
                "检修人员": r.检修人员,
                "检修内容": r.检修内容,
                "类型": r.类型,
            }
        )

    df = pd.DataFrame(data)
    from io import BytesIO

    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    output = make_response(buffer.read())
    output.headers["Content-Disposition"] = "attachment; filename=maintenance.xlsx"
    output.headers["Content-Type"] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    return output


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
