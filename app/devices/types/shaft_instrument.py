from app.models import DeviceBase, db


class ShaftInstrument(DeviceBase):
    __tablename__ = "shaft_instruments"

    序号 = db.Column(db.Integer)
    装置名称 = db.Column(db.String(100))
    位号 = db.Column(db.String(50))
    安装位置及用途 = db.Column(db.String(200))
    设备名称 = db.Column(db.String(100))
    设备等级 = db.Column(db.String(20))
    规格型号 = db.Column(db.String(100))
    生产厂家 = db.Column(db.String(100))
    测量范围 = db.Column(db.String(50))
    精度 = db.Column(db.String(50))
    是否联锁 = db.Column(db.String(10))
    联锁设定值 = db.Column(db.String(50))
    备注 = db.Column(db.Text)
