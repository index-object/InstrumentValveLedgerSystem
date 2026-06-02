from app.models import DeviceBase, db


class FlowMeter(DeviceBase):
    __tablename__ = "flow_meters"

    装置名称 = db.Column(db.String(100))
    位号 = db.Column(db.String(50))
    安装位置及用途 = db.Column(db.String(200))
    设备名称 = db.Column(db.String(100))
    设备分级 = db.Column(db.String(20))
    规格型号 = db.Column(db.String(100))
    生产厂家 = db.Column(db.String(100))
    量程_kpa = db.Column("量程（kpa）", db.String(50))
    测量范围 = db.Column(db.String(100))
    工艺介质 = db.Column("工艺介质 / 介质 名称", db.String(50))
    设计温度_C = db.Column("设计 温度℃", db.String(50))
    设计压力_MPa = db.Column("设计压力MPa", db.String(50))
    规格尺寸 = db.Column(db.String(100))
    规格尺寸连接方式 = db.Column(db.String(200))
    电源 = db.Column(db.String(50))
    输出信号 = db.Column(db.String(50))
    精度 = db.Column(db.String(50))
    是否伴热 = db.Column(db.String(10))
    是否_联锁 = db.Column("是否 联锁", db.String(50))
    编号 = db.Column(db.String(50))
    备注 = db.Column(db.Text)
