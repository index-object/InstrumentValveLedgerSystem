from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    send_from_directory,
    make_response,
)
from flask_login import login_required, current_user
from app.models import db, Valve, Setting, ApprovalLog, User
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
    search = request.args.get("search")
    if search:
        query = query.filter(
            (Valve.位号.contains(search))
            | (Valve.名称.contains(search))
            | (Valve.装置名称.contains(search))
        )

    valves_list = query.order_by(Valve.序号).all()
    return render_template("valves/list.html", valves=valves_list)


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


@valves.route("/my-applications")
@login_required
def my_applications():
    my_valves = (
        Valve.query.filter_by(created_by=current_user.id)
        .order_by(Valve.created_at.desc())
        .all()
    )
    return render_template("valves/my_applications.html", valves=my_valves)
