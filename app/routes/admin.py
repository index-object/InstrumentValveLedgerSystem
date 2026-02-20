from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models import db, User, Setting
from functools import wraps

admin = Blueprint("admin", __name__, url_prefix="/admin")


def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ["leader", "admin"]:
            flash("需要管理员权限")
            return redirect(url_for("valves.list"))
        return f(*args, **kwargs)

    return decorated_function


@admin.route("/")
@login_required
@require_admin
def index():
    user_count = User.query.filter_by(status="active").count()
    return render_template("admin/index.html", user_count=user_count)


@admin.route("/users", methods=["GET", "POST"])
@login_required
@require_admin
def users():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")
        real_name = request.form.get("real_name")
        dept = request.form.get("dept")

        if User.query.filter_by(username=username).first():
            flash("用户名已存在")
        else:
            user = User(username=username, role=role, real_name=real_name, dept=dept)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("用户添加成功")

    users_list = User.query.all()
    return render_template("admin/users.html", users=users_list)


@admin.route("/user/<int:id>/reset-password", methods=["POST"])
@login_required
@require_admin
def reset_password(id):
    user = User.query.get_or_404(id)
    user.set_password("123456")
    db.session.commit()
    flash(f"密码已重置为: 123456")
    return redirect(url_for("admin.users"))


@admin.route("/user/<int:id>/delete", methods=["POST"])
@login_required
@require_admin
def delete_user(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash("不能删除自己")
        return redirect(url_for("admin.users"))

    user.status = "inactive"
    db.session.commit()
    flash("用户已禁用")
    return redirect(url_for("admin.users"))


@admin.route("/settings", methods=["GET", "POST"])
@login_required
@require_admin
def settings():
    if request.method == "POST":
        settings_map = {
            "auto_approval": request.form.get("auto_approval"),
            "default_password": request.form.get("default_password"),
            "page_size": request.form.get("page_size"),
            "system_name": request.form.get("system_name"),
        }

        for key, value in settings_map.items():
            setting = Setting.query.get(key)
            if setting:
                setting.value = value
            else:
                setting = Setting(key=key, value=value)
                db.session.add(setting)

        db.session.commit()
        flash("设置已保存")

    settings = {}
    for key in ["auto_approval", "default_password", "page_size", "system_name"]:
        setting = Setting.query.get(key)
        settings[key] = setting.value if setting else None

    settings.setdefault("auto_approval", "true")
    settings.setdefault("default_password", "123456")
    settings.setdefault("page_size", "20")
    settings.setdefault("system_name", "仪表阀门台账系统")

    return render_template("admin/settings.html", **settings)
