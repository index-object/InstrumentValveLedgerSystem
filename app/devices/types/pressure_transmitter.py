from app.models import DeviceBase, db


class PressureTransmitter(DeviceBase):
    __tablename__ = "pressure_transmitters"

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
    电源 = db.Column(db.String(50))
    输出信号 = db.Column(db.String(50))
    编号 = db.Column(db.String(50))
    是否联锁 = db.Column(db.String(10))
    备注 = db.Column(db.Text)
