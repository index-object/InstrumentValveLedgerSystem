from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User
from datetime import datetime

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        remember = request.form.get("remember", False)
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=remember)
            if user.must_change_password:
                return redirect(url_for("auth.change_password"))
            return redirect(url_for("main.index"))
        else:
            flash("用户名或密码错误")

    return render_template("login.html")


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("两次输入的密码不一致")
            return redirect(url_for("auth.change_password"))

        if len(new_password) < 6:
            flash("密码长度至少6位")
            return redirect(url_for("auth.change_password"))

        current_user.set_password(new_password)
        current_user.must_change_password = False
        db.session.commit()
        flash("密码修改成功")
        return redirect(url_for("main.index"))

    return render_template("auth/change_password.html")
