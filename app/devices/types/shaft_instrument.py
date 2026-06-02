from app.models import DeviceBase, db


class ShaftInstrument(DeviceBase):
    __tablename__ = "shaft_instruments"

    装置名称 = db.Column(db.String(100))
    位号 = db.Column(db.String(50))
    安装位置及用途 = db.Column(db.String(200))
    设备名称 = db.Column(db.String(100))
    设备分级 = db.Column(db.String(20))
    规格型号 = db.Column(db.String(100))
    生产厂家 = db.Column(db.String(100))
    测量范围 = db.Column(db.String(50))
    精度 = db.Column(db.String(50))
    是否_联锁 = db.Column("是否 联锁", db.String(10))
    联锁_设定值 = db.Column("联锁 设定值", db.String(50))
    备注 = db.Column(db.Text)
