"""权限检查函数测试

测试细粒度权限控制：
- 台账合集权限：员工可创建/编辑自己的，领导无权限
- 阀门权限：员工可编辑自己的（排除pending状态），领导无权限
- 维护记录权限：员工可创建/编辑自己的，领导无权限
- 审批权限：仅领导和管理员可审批pending状态阀门
"""

import pytest
from flask_login import login_user
from app import db
from app.models import User, Ledger, Valve, MaintenanceRecord
from app.routes.valves.permissions import (
    can_create_ledger,
    can_edit_ledger,
    can_delete_ledger,
    can_create_valve,
    can_edit_valve,
    can_delete_valve,
    can_submit_valve,
    can_approve_valve,
    can_import_data,
    can_export_data,
    can_manage_attachments,
    can_manage_photos,
    can_create_maintenance,
    can_edit_maintenance,
    can_delete_maintenance,
    can_view_valve,
    can_view_ledger,
    EDITABLE_STATUSES,
)


class TestLedgerPermissions:
    """台账合集权限测试"""

    def test_employee_can_create_ledger(self, app, employee_user):
        """员工可以创建台账合集"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            with app.test_request_context():
                login_user(user)
                assert can_create_ledger() is True

    def test_leader_cannot_create_ledger(self, app, leader_user):
        """领导不能创建台账合集"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            with app.test_request_context():
                login_user(user)
                assert can_create_ledger() is False

    def test_admin_can_create_ledger(self, app, admin_user):
        """管理员可以创建台账合集"""
        with app.app_context():
            user = db.session.get(User, admin_user.id)
            with app.test_request_context():
                login_user(user)
                assert can_create_ledger() is True

    def test_employee_can_edit_own_ledger(self, app, employee_user, test_ledger):
        """员工可以编辑自己的台账合集"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_edit_ledger(ledger) is True

    def test_employee_cannot_edit_others_ledger(self, app, other_employee, test_ledger):
        """员工不能编辑他人的台账合集"""
        with app.app_context():
            user = db.session.get(User, other_employee.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_edit_ledger(ledger) is False

    def test_leader_cannot_edit_ledger(self, app, leader_user, test_ledger):
        """领导不能编辑台账合集"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_edit_ledger(ledger) is False

    def test_admin_can_edit_any_ledger(self, app, admin_user, test_ledger):
        """管理员可以编辑任意台账合集"""
        with app.app_context():
            user = db.session.get(User, admin_user.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_edit_ledger(ledger) is True

    def test_employee_can_delete_own_ledger(self, app, employee_user, test_ledger):
        """员工可以删除自己的台账合集（无pending阀门时）"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_delete_ledger(ledger) is True

    def test_leader_cannot_delete_ledger(self, app, leader_user, test_ledger):
        """领导不能删除台账合集"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_delete_ledger(ledger) is False

    def test_cannot_delete_ledger_with_pending_valves(self, app, employee_user):
        """有pending状态阀门时不能删除台账合集"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            # 创建有pending阀门的台账
            ledger = Ledger(
                名称="待审批台账",
                status="pending",
                created_by=user.id
            )
            db.session.add(ledger)
            db.session.commit()

            valve = Valve(
                ledger_id=ledger.id,
                位号="PENDING-001",
                名称="待审批阀门",
                status="pending",
                created_by=user.id
            )
            db.session.add(valve)
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_delete_ledger(ledger) is False


class TestValvePermissions:
    """阀门权限测试"""

    def test_employee_can_create_valve_in_own_ledger(self, app, employee_user, test_ledger):
        """员工可以在自己的台账合集里创建阀门"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_create_valve(ledger) is True

    def test_employee_cannot_create_valve_in_others_ledger(self, app, other_employee, test_ledger):
        """员工不能在他人的台账合集里创建阀门"""
        with app.app_context():
            user = db.session.get(User, other_employee.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_create_valve(ledger) is False

    def test_leader_cannot_create_valve(self, app, leader_user, test_ledger):
        """领导不能创建阀门"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_create_valve(ledger) is False

    def test_employee_can_edit_own_draft_valve(self, app, employee_user, test_valve):
        """员工可以编辑自己的草稿状态阀门"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "draft"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_edit_valve(valve) is True

    def test_employee_can_edit_own_rejected_valve(self, app, employee_user, test_valve):
        """员工可以编辑自己的已驳回状态阀门"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "rejected"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_edit_valve(valve) is True

    def test_employee_can_edit_own_approved_valve(self, app, employee_user, test_valve):
        """员工可以编辑自己的已审批状态阀门"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "approved"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_edit_valve(valve) is True

    def test_employee_cannot_edit_own_pending_valve(self, app, employee_user, test_valve):
        """员工不能编辑自己的待审批状态阀门"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "pending"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_edit_valve(valve) is False

    def test_employee_cannot_edit_others_valve(self, app, other_employee, test_valve):
        """员工不能编辑他人的阀门"""
        with app.app_context():
            user = db.session.get(User, other_employee.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "draft"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_edit_valve(valve) is False

    def test_leader_cannot_edit_valve(self, app, leader_user, test_valve):
        """领导不能编辑阀门"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "draft"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_edit_valve(valve) is False

    def test_admin_can_edit_any_valve(self, app, admin_user, test_valve):
        """管理员可以编辑任意阀门"""
        with app.app_context():
            user = db.session.get(User, admin_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "draft"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_edit_valve(valve) is True

    def test_delete_valve_same_as_edit(self, app, employee_user, test_valve):
        """删除阀门权限与编辑权限相同"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            valve = db.session.get(Valve, test_valve.id)

            for status in EDITABLE_STATUSES:
                valve.status = status
                db.session.commit()
                with app.test_request_context():
                    login_user(user)
                    assert can_delete_valve(valve) == can_edit_valve(valve)

    def test_employee_can_submit_own_draft_valve(self, app, employee_user, test_valve):
        """员工可以提交自己的草稿状态阀门"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "draft"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_submit_valve(valve) is True

    def test_employee_cannot_submit_pending_valve(self, app, employee_user, test_valve):
        """员工不能提交已处于pending状态的阀门"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "pending"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_submit_valve(valve) is False


class TestApprovalPermissions:
    """审批权限测试"""

    def test_leader_can_approve_pending_valve(self, app, leader_user, test_valve):
        """领导可以审批pending状态阀门"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "pending"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_approve_valve(valve) is True

    def test_leader_cannot_approve_non_pending_valve(self, app, leader_user, test_valve):
        """领导不能审批非pending状态阀门"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            valve = db.session.get(Valve, test_valve.id)

            for status in ["draft", "approved", "rejected"]:
                valve.status = status
                db.session.commit()
                with app.test_request_context():
                    login_user(user)
                    assert can_approve_valve(valve) is False

    def test_employee_cannot_approve_valve(self, app, employee_user, test_valve):
        """员工不能审批阀门"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "pending"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_approve_valve(valve) is False

    def test_admin_can_approve_pending_valve(self, app, admin_user, test_valve):
        """管理员可以审批pending状态阀门"""
        with app.app_context():
            user = db.session.get(User, admin_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "pending"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_approve_valve(valve) is True


class TestMaintenancePermissions:
    """维护记录权限测试"""

    def test_employee_can_create_maintenance(self, app, employee_user):
        """员工可以创建维护记录"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            with app.test_request_context():
                login_user(user)
                assert can_create_maintenance() is True

    def test_leader_cannot_create_maintenance(self, app, leader_user):
        """领导不能创建维护记录"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            with app.test_request_context():
                login_user(user)
                assert can_create_maintenance() is False

    def test_admin_can_create_maintenance(self, app, admin_user):
        """管理员可以创建维护记录"""
        with app.app_context():
            user = db.session.get(User, admin_user.id)
            with app.test_request_context():
                login_user(user)
                assert can_create_maintenance() is True

    def test_employee_can_edit_own_maintenance(self, app, employee_user, test_maintenance):
        """员工可以编辑自己创建的维护记录"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            record = db.session.get(MaintenanceRecord, test_maintenance.id)
            with app.test_request_context():
                login_user(user)
                assert can_edit_maintenance(record) is True

    def test_employee_cannot_edit_others_maintenance(self, app, other_employee, test_maintenance):
        """员工不能编辑他人创建的维护记录"""
        with app.app_context():
            user = db.session.get(User, other_employee.id)
            record = db.session.get(MaintenanceRecord, test_maintenance.id)
            with app.test_request_context():
                login_user(user)
                assert can_edit_maintenance(record) is False

    def test_leader_cannot_edit_maintenance(self, app, leader_user, test_maintenance):
        """领导不能编辑维护记录"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            record = db.session.get(MaintenanceRecord, test_maintenance.id)
            with app.test_request_context():
                login_user(user)
                assert can_edit_maintenance(record) is False

    def test_admin_can_edit_any_maintenance(self, app, admin_user, test_maintenance):
        """管理员可以编辑任意维护记录"""
        with app.app_context():
            user = db.session.get(User, admin_user.id)
            record = db.session.get(MaintenanceRecord, test_maintenance.id)
            with app.test_request_context():
                login_user(user)
                assert can_edit_maintenance(record) is True

    def test_delete_maintenance_same_as_edit(self, app, employee_user, test_maintenance):
        """删除维护记录权限与编辑权限相同"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            record = db.session.get(MaintenanceRecord, test_maintenance.id)
            with app.test_request_context():
                login_user(user)
                assert can_delete_maintenance(record) == can_edit_maintenance(record)


class TestImportExportPermissions:
    """导入导出权限测试"""

    def test_employee_can_import_own_ledger(self, app, employee_user, test_ledger):
        """员工可以在自己的台账合集中导入数据"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_import_data(ledger) is True

    def test_employee_cannot_import_others_ledger(self, app, other_employee, test_ledger):
        """员工不能在他人的台账合集中导入数据"""
        with app.app_context():
            user = db.session.get(User, other_employee.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_import_data(ledger) is False

    def test_leader_cannot_import(self, app, leader_user, test_ledger):
        """领导不能导入数据"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_import_data(ledger) is False

    def test_admin_can_import_any_ledger(self, app, admin_user, test_ledger):
        """管理员可以在任意台账合集中导入数据"""
        with app.app_context():
            user = db.session.get(User, admin_user.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_import_data(ledger) is True

    def test_everyone_can_export(self, app, employee_user, leader_user, admin_user):
        """所有用户都可以导出数据"""
        with app.app_context():
            for user in [employee_user, leader_user, admin_user]:
                user_obj = db.session.get(User, user.id)
                with app.test_request_context():
                    login_user(user_obj)
                    assert can_export_data() is True


class TestAttachmentPhotoPermissions:
    """附件和照片权限测试"""

    def test_attachment_permission_same_as_valve_edit(self, app, employee_user, test_valve):
        """附件管理权限与阀门编辑权限相同"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            valve = db.session.get(Valve, test_valve.id)

            for status in EDITABLE_STATUSES + ["pending"]:
                valve.status = status
                db.session.commit()
                with app.test_request_context():
                    login_user(user)
                    assert can_manage_attachments(valve) == can_edit_valve(valve)

    def test_photo_permission_same_as_valve_edit(self, app, employee_user, test_valve):
        """照片管理权限与阀门编辑权限相同"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            valve = db.session.get(Valve, test_valve.id)

            for status in EDITABLE_STATUSES + ["pending"]:
                valve.status = status
                db.session.commit()
                with app.test_request_context():
                    login_user(user)
                    assert can_manage_photos(valve) == can_edit_valve(valve)

    def test_leader_cannot_manage_attachments(self, app, leader_user, test_valve):
        """领导不能管理附件"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "draft"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_manage_attachments(valve) is False

    def test_leader_cannot_manage_photos(self, app, leader_user, test_valve):
        """领导不能管理照片"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            valve = db.session.get(Valve, test_valve.id)
            valve.status = "draft"
            db.session.commit()

            with app.test_request_context():
                login_user(user)
                assert can_manage_photos(valve) is False


class TestViewPermissions:
    """查看权限测试（兼容性测试）"""

    def test_employee_can_view_own_valve(self, app, employee_user, test_valve):
        """员工可以查看自己的阀门"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            valve = db.session.get(Valve, test_valve.id)
            with app.test_request_context():
                login_user(user)
                assert can_view_valve(valve) is True

    def test_leader_can_view_any_valve(self, app, leader_user, test_valve):
        """领导可以查看任意阀门"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            valve = db.session.get(Valve, test_valve.id)
            with app.test_request_context():
                login_user(user)
                assert can_view_valve(valve) is True

    def test_employee_can_view_own_ledger(self, app, employee_user, test_ledger):
        """员工可以查看自己的台账合集"""
        with app.app_context():
            user = db.session.get(User, employee_user.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_view_ledger(ledger) is True

    def test_leader_can_view_any_ledger(self, app, leader_user, test_ledger):
        """领导可以查看任意台账合集"""
        with app.app_context():
            user = db.session.get(User, leader_user.id)
            ledger = db.session.get(Ledger, test_ledger.id)
            with app.test_request_context():
                login_user(user)
                assert can_view_ledger(ledger) is True


class TestEditableStatuses:
    """可编辑状态常量测试"""

    def test_editable_statuses_defined(self):
        """验证可编辑状态定义正确"""
        assert EDITABLE_STATUSES == ["draft", "rejected", "approved"]

    def test_pending_not_in_editable_statuses(self):
        """pending状态不在可编辑状态中"""
        assert "pending" not in EDITABLE_STATUSES