from app.models import DeviceBase, DevicePhotoMixin, db


class ElectricValve(DeviceBase, DevicePhotoMixin):
    __tablename__ = "electric_valves"

    装置名称 = db.Column(db.String(100))
    位号 = db.Column(db.String(50))
    名称 = db.Column(db.String(100))
    安装位置及用途 = db.Column(db.String(200))
    设备等级 = db.Column(db.String(20))
    型号规格 = db.Column(db.String(100))
    生产厂家 = db.Column(db.String(100))
    设备编号 = db.Column(db.String(100))

    介质名称 = db.Column(db.String(50))
    设计温度_c = db.Column("设计温度℃", db.String(50))
    操作压力 = db.Column(db.String(50))
    设计压力 = db.Column(db.String(50))
    公称通径 = db.Column(db.String(50))

    阀体 = db.Column(db.String(100))
    阀体材质 = db.Column(db.String(50))
    阀座材质 = db.Column(db.String(50))
    阀芯材质 = db.Column(db.String(50))

    流量特性 = db.Column(db.String(50))
    泄露等级 = db.Column(db.String(50))

    转矩Nm = db.Column(db.String(50))
    功率 = db.Column(db.String(50))
    转速r_per_min = db.Column(db.String(50))
    转圈数r = db.Column(db.String(50))
    电源 = db.Column(db.String(50))
    防护等级 = db.Column(db.String(50))

    作用形式 = db.Column(db.String(50))
    额定行程 = db.Column(db.String(50))

    是否联锁 = db.Column(db.String(10))
    备注 = db.Column(db.Text)

    def __getattr__(self, name):
        # Return None for ValveBase-style fields so existing
        # templates (list.html) that reference prefixed field names
        # (e.g. 工艺条件_介质名称) don't crash for electric valves.
        if name.startswith('工艺条件_') or name.startswith('阀体_') \
                or name.startswith('阀内件_') or name.startswith('执行机构_'):
            return None
        raise AttributeError(name)
