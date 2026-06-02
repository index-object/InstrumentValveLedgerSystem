from app.models import DeviceBase, db


class LevelTransmitter(DeviceBase):
    __tablename__ = "level_transmitters"

    装置名称 = db.Column(db.String(100))
    位号 = db.Column(db.String(50))
    安装位置及用途 = db.Column(db.String(200))
    设备名称 = db.Column(db.String(100))
    设备分级 = db.Column(db.String(20))
    规格型号 = db.Column(db.String(200))
    生产厂家 = db.Column(db.String(100))
    介质 = db.Column(db.String(50))
    液位范围_mm = db.Column("液位范围/mm", db.String(50))
    精度_mm = db.Column("精度/mm", db.String(50))
    密度_g_cm3 = db.Column("密度g/cm3", db.String(50))
    电源 = db.Column(db.String(50))
    输出信号 = db.Column(db.String(50))
    连接方式及规格 = db.Column(db.String(200))
    出厂编号 = db.Column(db.String(50))
    是否联锁 = db.Column(db.String(50))
    备注 = db.Column(db.Text)
