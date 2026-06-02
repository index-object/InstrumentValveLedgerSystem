from app.models import DeviceBase, db


class LocalTemperature(DeviceBase):
    __tablename__ = "local_temperatures"

    装置名称 = db.Column(db.String(100))
    位号 = db.Column(db.String(50))
    安装位置及用途 = db.Column(db.String(200))
    介质 = db.Column(db.String(50))
    设备名称 = db.Column(db.String(100))
    设备分级 = db.Column(db.String(20))
    规格型号 = db.Column(db.String(100))
    生产厂家 = db.Column(db.String(100))
    测量范围_C = db.Column("测量范围/℃", db.String(50))
    插入深度_mm = db.Column("插入深度/mm", db.String(50))
    连接方式及规格 = db.Column(db.String(200))
    精度 = db.Column(db.String(50))
    法兰规格及材质 = db.Column(db.String(200))
    出厂编号 = db.Column(db.String(50))
    备注 = db.Column(db.Text)
