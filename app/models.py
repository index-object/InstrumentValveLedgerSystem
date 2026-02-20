from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(
        db.String(20), nullable=False, default="employee"
    )  # employee/leader
    real_name = db.Column(db.String(50))
    dept = db.Column(db.String(50))
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Valve(db.Model):
    __tablename__ = "valves"
    id = db.Column(db.Integer, primary_key=True)
    # 基本信息
    序号 = db.Column(db.String(20))
    装置名称 = db.Column(db.String(100))
    位号 = db.Column(db.String(50), unique=True)
    名称 = db.Column(db.String(100))
    设备等级 = db.Column(db.String(20))
    型号规格 = db.Column(db.String(100))
    生产厂家 = db.Column(db.String(100))
    安装位置及用途 = db.Column(db.String(200))
    # 工艺条件
    工艺条件_介质名称 = db.Column(db.String(50))
    工艺条件_设计温度 = db.Column(db.String(50))
    工艺条件_阀前压力 = db.Column(db.String(50))
    工艺条件_阀后压力 = db.Column(db.String(50))
    # 阀体
    阀体_公称通径 = db.Column(db.String(50))
    阀体_连接方式及规格 = db.Column(db.String(100))
    阀体_材质 = db.Column(db.String(50))
    # 阀内件
    阀内件_阀座直径 = db.Column(db.String(50))
    阀内件_阀芯材质 = db.Column(db.String(50))
    阀内件_阀座材质 = db.Column(db.String(50))
    阀内件_阀杆材质 = db.Column(db.String(50))
    阀内件_流量特性 = db.Column(db.String(50))
    阀内件_泄露等级 = db.Column(db.String(50))
    阀内件_Cv值 = db.Column(db.String(50))
    # 执行机构
    执行机构_形式 = db.Column(db.String(50))
    执行机构_型号规格 = db.Column(db.String(100))
    执行机构_厂家 = db.Column(db.String(100))
    执行机构_作用形式 = db.Column(db.String(50))
    执行机构_行程 = db.Column(db.String(50))
    执行机构_弹簧范围 = db.Column(db.String(50))
    执行机构_气源压力 = db.Column(db.String(50))
    执行机构_故障位置 = db.Column(db.String(50))
    执行机构_关阀时间 = db.Column(db.String(50))
    执行机构_开阀时间 = db.Column(db.String(50))
    # 其他
    设备编号 = db.Column(db.String(50))
    是否联锁 = db.Column(db.String(10))
    备注 = db.Column(db.Text)
    # 状态与审批
    status = db.Column(
        db.String(20), default="draft"
    )  # draft/pending/approved/rejected
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    creator = db.relationship("User", foreign_keys=[created_by])
    approver = db.relationship("User", foreign_keys=[approved_by])


class ValvePhoto(db.Model):
    __tablename__ = "valve_photos"
    id = db.Column(db.Integer, primary_key=True)
    valve_id = db.Column(db.Integer, db.ForeignKey("valves.id"), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(200))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    valve = db.relationship("Valve", backref="photos")
    uploader = db.relationship("User")


class MaintenanceRecord(db.Model):
    __tablename__ = "maintenance_records"
    id = db.Column(db.Integer, primary_key=True)
    valve_id = db.Column(db.Integer, db.ForeignKey("valves.id"), nullable=False)
    所属中心 = db.Column(db.String(100))
    设备位号 = db.Column(db.String(50))
    设备名称 = db.Column(db.String(100))
    检修时间 = db.Column(db.DateTime)
    检修内容 = db.Column(db.Text)
    检修人员 = db.Column(db.String(50))
    类型 = db.Column(db.String(50))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    valve = db.relationship("Valve", backref="maintenance_records")
    creator = db.relationship("User")


class ValveAttachment(db.Model):
    __tablename__ = "valve_attachments"
    id = db.Column(db.Integer, primary_key=True)
    valve_id = db.Column(db.Integer, db.ForeignKey("valves.id"), nullable=False)
    名称 = db.Column(db.String(100))
    设备等级 = db.Column(db.String(20))
    型号规格 = db.Column(db.String(100))
    生产厂家 = db.Column(db.String(100))
    type = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    valve = db.relationship("Valve", backref="attachments")


class ApprovalLog(db.Model):
    __tablename__ = "approval_logs"
    id = db.Column(db.Integer, primary_key=True)
    valve_id = db.Column(db.Integer, db.ForeignKey("valves.id"), nullable=False)
    action = db.Column(db.String(20))  # submit/approve/reject
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    valve = db.relationship("Valve", backref="approval_logs")
    user = db.relationship("User")


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200))
