from app.models import DeviceBase, db


class LocalPressureGauge(DeviceBase):
    __tablename__ = "local_pressure_gauges"

    装置名称 = db.Column(db.String(100))
    位号 = db.Column(db.String(50))
    安装位置及用途 = db.Column(db.String(200))
    设备名称 = db.Column(db.String(100))
    设备分级 = db.Column(db.String(20))
    规格型号 = db.Column(db.String(100))
    生产厂家 = db.Column(db.String(100))
    介质 = db.Column(db.String(50))
    测量范围Mpa = db.Column(db.String(50))
    连接方式及规格 = db.Column(db.String(100))
    精度 = db.Column(db.String(50))
    编号 = db.Column(db.String(50))
    备注 = db.Column(db.Text)
