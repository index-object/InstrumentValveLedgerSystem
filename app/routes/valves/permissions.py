from flask import flash, redirect, url_for
from flask_login import current_user
from functools import wraps


def can_edit_valve(valve):
    """检查当前用户是否可以编辑台账"""
    return valve.created_by == current_user.id or current_user.role in [
        "leader",
        "admin",
    ]


def can_delete_valve(valve):
    """检查当前用户是否可以删除台账"""
    return can_edit_valve(valve)


def can_view_valve(valve):
    """查看台账权限"""
    if valve.created_by == current_user.id:
        return True
    if current_user.role in ["leader", "admin"]:
        return True
    if valve.status == "approved":
        return True
    return False


def can_view_ledger(ledger):
    """查看台账集合权限"""
    if ledger.created_by == current_user.id:
        return True
    if current_user.role in ["leader", "admin"]:
        return True
    if ledger.status == "approved":
        return True
    return False


def require_leader(f):
    """装饰器：要求领导权限"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ["leader", "admin"]:
            flash("需要领导权限")
            return redirect(url_for("valves.list"))
        return f(*args, **kwargs)

    return decorated_function


def require_edit_permission(valve):
    """检查编辑权限，返回错误信息或None"""
    if not can_edit_valve(valve):
        return "无权编辑"
    if valve.status not in ["draft", "rejected", "approved"]:
        return "当前状态无法编辑"
    return None


def require_delete_permission(valve):
    """检查删除权限，返回错误信息或None"""
    if not can_delete_valve(valve):
        return "无权删除"
    if valve.status not in ["draft", "rejected"]:
        return "当前状态无法删除"
    return None
