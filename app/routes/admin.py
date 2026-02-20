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
