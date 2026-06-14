from app.models import DeviceBase, db


class Temperature(DeviceBase):
    __tablename__ = "temperatures"

    序号 = db.Column(db.Integer)
    装置名称 = db.Column(db.String(100))
    位号 = db.Column(db.String(50))
    安装位置及用途 = db.Column(db.String(200))
    设备名称 = db.Column(db.String(100))
    设备等级 = db.Column(db.String(20))
    分度号 = db.Column(db.String(50))
    规格型号 = db.Column(db.String(200))
    生产厂家 = db.Column(db.String(200))
    介质 = db.Column(db.String(50))
    测量范围 = db.Column(db.String(50))
    插入深度 = db.Column(db.String(50))
    连接方式及规格 = db.Column(db.String(200))
    精度 = db.Column(db.String(50))
    套管规格及材质 = db.Column(db.String(200))
    出厂编号 = db.Column(db.String(50))
    是否联锁 = db.Column(db.String(50))
    备注 = db.Column(db.Text)
