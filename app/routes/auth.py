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
            return redirect(url_for("main.index"))
        else:
            flash("用户名或密码错误")

    return render_template("login.html")


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
