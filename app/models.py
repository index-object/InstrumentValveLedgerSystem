from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import declared_attr

db = SQLAlchemy()

# Forward declarations for type hints
ControlValve = None
OnOffValve = None


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(
        db.String(20), nullable=False, default="employee"
    )  # employee/leader/admin
    real_name = db.Column(db.String(50))
    dept = db.Column(db.String(50))
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)
    must_change_password = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Ledger(db.Model):
    __tablename__ = "ledgers"
    id = db.Column(db.Integer, primary_key=True)

    名称 = db.Column(db.String(100), nullable=False)
    描述 = db.Column(db.Text)
    类型 = db.Column(db.String(50), nullable=False, default="valve")

    status = db.Column(db.String(20), default="draft")

    valve_count = db.Column(db.Integer, default=0)
    pending_count = db.Column(db.Integer, default=0)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    approved_snapshot_status = db.Column(db.String(20), nullable=True)
    approved_snapshot_at = db.Column(db.DateTime, nullable=True)

    creator = db.relationship("User", foreign_keys=[created_by])
    approver = db.relationship("User", foreign_keys=[approved_by])


class DeviceBase(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    ledger_id = db.Column(db.Integer, db.ForeignKey("ledgers.id"), nullable=True)
    status = db.Column(db.String(20), default="draft")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @declared_attr
    def creator(cls):
        return db.relationship("User", foreign_keys=[cls.created_by])

    @declared_attr
    def approver(cls):
        return db.relationship("User", foreign_keys=[cls.approved_by])


class DevicePhotoMixin:
    """为阀门模型混入附件相关快捷属性"""

    @property
    def attachments(self):
        from app.models import ValveAttachment
        from app.devices.valve_helper import get_valve_ledger_type
        device_type = get_valve_ledger_type(self)
        if not device_type:
            return []
        return ValveAttachment.query.filter_by(
            device_type=device_type,
            device_id=self.id,
        ).all()

    @property
    def maintenance_records(self):
        from app.models import MaintenanceRecord
        from app.devices.valve_helper import get_valve_ledger_type
        from flask_login import current_user
        device_type = get_valve_ledger_type(self)
        if not device_type:
            return []
        q = MaintenanceRecord.query.filter_by(
            device_type=device_type,
            device_id=self.id,
        )
        if current_user.is_authenticated and current_user.role == "employee":
            q = q.filter(MaintenanceRecord.created_by == current_user.id)
        return q.order_by(MaintenanceRecord.检修时间.desc()).all()

    @property
    def photos(self):
        from app.models import ValvePhoto
        from app.devices.valve_helper import get_valve_ledger_type
        device_type = get_valve_ledger_type(self)
        if not device_type:
            return []
        return ValvePhoto.query.filter_by(
            device_type=device_type,
            device_id=self.id,
        ).all()

    @property
    def documents(self):
        from app.models import ValveDocument
        from app.devices.valve_helper import get_valve_ledger_type
        device_type = get_valve_ledger_type(self)
        if not device_type:
            return []
        return ValveDocument.query.filter_by(
            device_type=device_type,
            device_id=self.id,
        ).order_by(ValveDocument.uploaded_at.desc()).all()

    @property
    def attachments_json(self):
        return [
            {
                "id": att.id,
                "attachment_type": att.type,
                "name": att.名称,
                "device_grade": att.设备等级,
                "model": att.型号规格,
                "manufacturer": att.生产厂家,
            }
            for att in self.attachments
        ]


class ValvePhoto(db.Model):
    __tablename__ = "valve_photos"
    id = db.Column(db.Integer, primary_key=True)
    device_type = db.Column(db.String(20), nullable=False)
    device_id = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(200))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship("User")


class ValveFile(db.Model):
    __tablename__ = "valve_files"
    id = db.Column(db.Integer, primary_key=True)
    file_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    filename = db.Column(db.String(200), nullable=False)
    file_size = db.Column(db.Integer)
    ref_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ValveDocument(db.Model):
    __tablename__ = "valve_documents"
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey("valve_files.id"), nullable=True)
    device_type = db.Column(db.String(20), nullable=False)
    device_id = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(200))
    file_type = db.Column(db.String(10))
    file_size = db.Column(db.Integer)
    description = db.Column(db.String(200))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship("User")
    valve_file = db.relationship("ValveFile", backref="documents")


class MaintenanceRecord(db.Model):
    __tablename__ = "maintenance_records"
    id = db.Column(db.Integer, primary_key=True)
    device_type = db.Column(db.String(20), nullable=False)
    device_id = db.Column(db.Integer, nullable=False)
    装置名称 = db.Column(db.String(100))
    设备位号 = db.Column(db.String(50))
    设备名称 = db.Column(db.String(100))
    检修时间 = db.Column(db.DateTime)
    检修内容 = db.Column(db.Text)
    检修人员 = db.Column(db.String(50))
    类型 = db.Column(db.String(50))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    valve_deleted = db.Column(db.Boolean, default=False)

    creator = db.relationship("User")


class ValveAttachment(db.Model):
    __tablename__ = "valve_attachments"
    id = db.Column(db.Integer, primary_key=True)
    device_type = db.Column(db.String(20), nullable=False)
    device_id = db.Column(db.Integer, nullable=False)
    名称 = db.Column(db.String(100))
    设备等级 = db.Column(db.String(20))
    型号规格 = db.Column(db.String(100))
    生产厂家 = db.Column(db.String(100))
    type = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ApprovalLog(db.Model):
    __tablename__ = "approval_logs"
    id = db.Column(db.Integer, primary_key=True)
    ledger_id = db.Column(db.Integer, db.ForeignKey("ledgers.id"))
    device_type = db.Column(db.String(50), nullable=False)
    device_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(20))  # submit/approve/reject
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    ledger = db.relationship("Ledger", backref="approval_logs")
    user = db.relationship("User")


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200))


class SheetMapping(db.Model):
    __tablename__ = "sheet_mappings"

    id = db.Column(db.Integer, primary_key=True)
    sheet_name = db.Column(db.String(200), unique=True, nullable=False)
    type_code = db.Column(db.String(50), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    creator = db.relationship("User", foreign_keys=[created_by])


class MaintenancePlan(db.Model):
    __tablename__ = "maintenance_plans"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="draft")
    total_items = db.Column(db.Integer, default=0)
    completed_items = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    published_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship("User", foreign_keys=[created_by])
    publisher = db.relationship("User", foreign_keys=[published_by])
    items = db.relationship("MaintenancePlanItem", backref="plan", lazy="dynamic",
                            cascade="all, delete-orphan",
                            order_by="MaintenancePlanItem.planned_date_end")
    recipients = db.relationship("User", secondary="plan_recipients",
                                 backref=db.backref("assigned_plans", lazy="dynamic"))


class MaintenancePlanItem(db.Model):
    __tablename__ = "maintenance_plan_items"
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("maintenance_plans.id"), nullable=False)
    device_type = db.Column(db.String(20), nullable=False)
    device_id = db.Column(db.Integer, nullable=False)
    tag = db.Column(db.String(50), nullable=False)
    device_name = db.Column(db.String(100))
    planned_date_start = db.Column(db.Date, nullable=False)
    planned_date_end = db.Column(db.Date, nullable=False)
    maintenance_project = db.Column(db.Text)
    maintenance_scheme = db.Column(db.Text)
    safety_measures = db.Column(db.Text)
    project_leader = db.Column(db.String(50))
    maintenance_leader = db.Column(db.String(50))
    quality_acceptance = db.Column(db.Text)
    remark = db.Column(db.Text)
    group_id = db.Column(db.Integer)
    status = db.Column(db.String(20), nullable=False, default="pending")
    maintenance_id = db.Column(db.Integer, db.ForeignKey("maintenance_records.id"))
    completed_at = db.Column(db.DateTime)
    completed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    maintenance_record = db.relationship("MaintenanceRecord")
    completer = db.relationship("User", foreign_keys=[completed_by])


class PlanRecipient(db.Model):
    __tablename__ = "plan_recipients"
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("maintenance_plans.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    ref_type = db.Column(db.String(20))
    ref_id = db.Column(db.Integer)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="notifications")
