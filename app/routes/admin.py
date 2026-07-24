from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.models import db, User, Setting, SheetMapping
from app.utils.import_cache import get_import_cache_files, cleanup_import_cache
from functools import wraps

admin = Blueprint("admin", __name__, url_prefix="/admin")


def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != "admin":
            flash("需要管理员权限")
            return redirect(url_for("valves.list"))
        return f(*args, **kwargs)

    return decorated_function


@admin.route("/")
@login_required
@require_admin
def index():
    user_count = User.query.filter_by(status="active").count()
    mappings_count = SheetMapping.query.count()
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    cache_files = get_import_cache_files(upload_folder)
    return render_template(
        "admin/index.html",
        user_count=user_count,
        mappings_count=mappings_count,
        cache_count=len(cache_files),
    )


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
    user.must_change_password = True
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


@admin.route("/user/<int:id>/edit", methods=["GET", "POST"])
@login_required
@require_admin
def edit_user(id):
    user = User.query.get_or_404(id)

    if request.method == "POST":
        user.username = request.form.get("username")
        user.role = request.form.get("role")
        user.real_name = request.form.get("real_name")
        user.dept = request.form.get("dept")

        new_password = request.form.get("new_password")
        if new_password:
            user.set_password(new_password)

        db.session.commit()
        flash(f"用户 {user.username} 信息已更新")
        return redirect(url_for("admin.users"))

    return render_template("admin/edit_user.html", user=user)


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
    settings.setdefault("system_name", "仪表阀门智能管理系统")

    return render_template("admin/settings.html", **settings)


@admin.route("/sheet-mappings")
@login_required
@require_admin
def sheet_mappings():
    mappings = SheetMapping.query.order_by(
        SheetMapping.updated_at.desc()
    ).all()
    return render_template(
        "admin/sheet_mappings.html",
        mappings=mappings,
    )


@admin.route("/sheet-mappings/<int:id>/delete", methods=["POST"])
@login_required
@require_admin
def delete_sheet_mapping(id):
    mapping = SheetMapping.query.get_or_404(id)
    db.session.delete(mapping)
    db.session.commit()
    flash(f"已删除映射: {mapping.sheet_name} → {mapping.type_code}")
    return redirect(url_for("admin.sheet_mappings"))


@admin.route("/import-cache", methods=["GET", "POST"])
@login_required
@require_admin
def import_cache():
    upload_folder = current_app.config.get("UPLOAD_FOLDER")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_retention":
            val = request.form.get("retention_count", "30")
            if val.isdigit() and int(val) > 0:
                setting = Setting.query.get("import_cache_retention")
                if setting:
                    setting.value = val
                else:
                    setting = Setting(key="import_cache_retention", value=val)
                    db.session.add(setting)
                db.session.commit()
                flash(f"导入缓存保留次数已更新为 {val}")
            else:
                flash("请输入有效的正整数", "error")

        elif action == "delete":
            filename = request.form.get("filename")
            if filename:
                import os
                path = os.path.join(upload_folder, filename)
                try:
                    os.remove(path)
                    flash(f"已删除: {filename}")
                except OSError:
                    flash(f"删除失败: {filename}", "error")

        elif action == "cleanup_now":
            retention = Setting.query.get("import_cache_retention")
            max_keep = int(retention.value) if retention else 30
            deleted = cleanup_import_cache(upload_folder, max_keep)
            flash(f"已清理 {deleted} 个过期缓存文件")

        elif action == "cleanup_all":
            import os
            files = get_import_cache_files(upload_folder)
            count = 0
            for f in files:
                try:
                    os.remove(f["path"])
                    count += 1
                except OSError:
                    pass
            flash(f"已删除全部 {count} 个缓存文件")

        return redirect(url_for("admin.import_cache"))

    cur = Setting.query.get("import_cache_retention")
    retention = int(cur.value) if cur else 30
    files = get_import_cache_files(upload_folder)
    return render_template("admin/import_cache.html", files=files, retention=retention)
