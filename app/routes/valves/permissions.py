"""细粒度权限检查函数

权限规则：
- 员工(employee)：可CRUD自己的台账合集和阀门，只读查看所有台账
- 领导(leader)：只能审批/驳回pending状态的阀门，不能编辑任何内容
- 管理员(admin)：拥有全部权限

可编辑状态：draft, rejected, approved（排除pending）
"""

from flask import flash, redirect, url_for
from flask_login import current_user
from functools import wraps

# 可编辑的阀门状态（排除pending）
EDITABLE_STATUSES = ["draft", "rejected", "approved"]


# ========== 台账合集权限 ==========


def can_create_ledger():
    """检查当前用户是否可以创建台账合集

    员工和管理员可以创建，领导不能创建
    """
    return current_user.role in ["employee", "admin"]


def can_edit_ledger(ledger):
    """检查当前用户是否可以编辑台账合集

    管理员可编辑任意台账，员工只能编辑自己创建的台账
    领导不能编辑台账
    """
    if current_user.role == "admin":
        return True
    if current_user.role == "employee":
        return ledger.created_by == current_user.id
    return False


def can_delete_ledger(ledger):
    """检查当前用户是否可以删除台账合集

    需要同时满足：
    1. 有编辑权限
    2. 台账中没有pending状态的阀门
    """
    if not can_edit_ledger(ledger):
        return False
    # 检查是否有pending状态的阀门
    from app.models import Valve

    pending_count = Valve.query.filter_by(
        ledger_id=ledger.id, status="pending"
    ).count()
    return pending_count == 0


def can_view_ledger(ledger):
    """查看台账合集权限

    员工可以查看自己的台账和已审批的台账
    领导和管理员可以查看所有台账
    """
    if ledger.created_by == current_user.id:
        return True
    if current_user.role in ["leader", "admin"]:
        return True
    if ledger.approved_snapshot_status == "approved":
        return True
    return False


# ========== 阀门权限 ==========


def can_create_valve(ledger):
    """检查当前用户是否可以在指定台账中创建阀门

    管理员可以在任意台账创建，员工只能在自己的台账中创建
    领导不能创建阀门
    """
    if current_user.role == "admin":
        return True
    if current_user.role == "employee":
        return ledger.created_by == current_user.id
    return False


def can_edit_valve(valve):
    """检查当前用户是否可以编辑阀门

    需要同时满足：
    1. 管理员可编辑任意阀门，员工只能编辑自己创建的阀门
    2. 阀门状态在可编辑状态列表中（draft/rejected/approved）
    领导不能编辑阀门
    """
    # 管理员可以编辑任意阀门
    if current_user.role == "admin":
        return valve.status in EDITABLE_STATUSES
    # 员工只能编辑自己的阀门，且状态可编辑
    if current_user.role == "employee":
        return (
            valve.created_by == current_user.id
            and valve.status in EDITABLE_STATUSES
        )
    # 领导不能编辑
    return False


def can_delete_valve(valve):
    """检查当前用户是否可以删除阀门

    删除权限与编辑权限相同
    """
    return can_edit_valve(valve)


def can_view_valve(valve):
    """查看阀门权限

    员工可以查看自己的阀门和已审批的阀门
    领导和管理员可以查看所有阀门
    """
    if valve.created_by == current_user.id:
        return True
    if current_user.role in ["leader", "admin"]:
        return True
    if valve.status == "approved":
        return True
    return False


def can_submit_valve(valve):
    """检查当前用户是否可以提交阀门审批

    需要同时满足：
    1. 管理员或员工创建者
    2. 阀门状态为draft
    """
    if valve.status != "draft":
        return False
    if current_user.role == "admin":
        return True
    if current_user.role == "employee":
        return valve.created_by == current_user.id
    return False


def can_approve_valve(valve):
    """检查当前用户是否可以审批阀门

    需要同时满足：
    1. 用户角色为leader或admin
    2. 阀门状态为pending
    """
    if valve.status != "pending":
        return False
    return current_user.role in ["leader", "admin"]


# ========== 附件和照片权限 ==========


def can_manage_attachments(valve):
    """检查当前用户是否可以管理阀门附件

    附件管理权限与阀门编辑权限相同
    """
    return can_edit_valve(valve)


def can_manage_photos(valve):
    """检查当前用户是否可以管理阀门照片

    照片管理权限与阀门编辑权限相同
    """
    return can_edit_valve(valve)


# ========== 导入导出权限 ==========


def can_import_data(ledger):
    """检查当前用户是否可以在指定台账中导入数据

    管理员可以在任意台账导入，员工只能在自己的台账中导入
    领导不能导入数据
    """
    if current_user.role == "admin":
        return True
    if current_user.role == "employee":
        return ledger.created_by == current_user.id
    return False


def can_export_data():
    """检查当前用户是否可以导出数据

    所有登录用户都可以导出数据
    """
    return True


# ========== 维护记录权限 ==========


def can_create_maintenance():
    """检查当前用户是否可以创建维护记录

    员工和管理员可以创建，领导不能创建
    """
    return current_user.role in ["employee", "admin"]


def can_edit_maintenance(record):
    """检查当前用户是否可以编辑维护记录

    管理员可编辑任意记录，员工只能编辑自己创建的记录
    领导不能编辑维护记录
    """
    if current_user.role == "admin":
        return True
    if current_user.role == "employee":
        return record.created_by == current_user.id
    return False


def can_delete_maintenance(record):
    """检查当前用户是否可以删除维护记录

    删除权限与编辑权限相同
    """
    return can_edit_maintenance(record)


# ========== 兼容性函数（保持向后兼容） ==========


def require_edit_permission(valve):
    """检查编辑权限，返回错误信息或None

    保持向后兼容的函数
    """
    if not can_edit_valve(valve):
        if current_user.role == "leader":
            return "领导无权编辑阀门"
        return "无权编辑此阀门"
    if valve.status not in EDITABLE_STATUSES:
        return f"当前状态（{valve.status}）无法编辑"
    return None


def require_delete_permission(valve):
    """检查删除权限，返回错误信息或None

    保持向后兼容的函数
    """
    if not can_delete_valve(valve):
        if current_user.role == "leader":
            return "领导无权删除阀门"
        return "无权删除此阀门"
    if valve.status not in EDITABLE_STATUSES:
        return f"当前状态（{valve.status}）无法删除"
    return None


# ========== 装饰器 ==========


def require_leader(f):
    """装饰器：要求领导权限"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ["leader", "admin"]:
            flash("需要领导权限")
            return redirect(url_for("valves.list"))
        return f(*args, **kwargs)

    return decorated_function


def require_employee(f):
    """装饰器：要求员工权限（所有登录用户都有）"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ["employee", "leader", "admin"]:
            flash("需要员工权限")
            return redirect(url_for("valves.list"))
        return f(*args, **kwargs)

    return decorated_function


def require_employee_or_admin(f):
    """装饰器：要求员工或管理员权限（排除领导）

    用于导入功能，领导不能导入数据。
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ["employee", "admin"]:
            flash("需要员工或管理员权限")
            return redirect(url_for("valves.list"))
        return f(*args, **kwargs)

    return decorated_function