from app.models import DeviceBase, DevicePhotoMixin, db


class ValveBase(DeviceBase, DevicePhotoMixin):
    __abstract__ = True

    装置名称 = db.Column(db.String(100))
    位号 = db.Column(db.String(50))
    名称 = db.Column(db.String(100))
    设备等级 = db.Column(db.String(20))
    型号规格 = db.Column(db.String(100))
    生产厂家 = db.Column(db.String(100))
    安装位置及用途 = db.Column(db.String(200))

    工艺条件_介质名称 = db.Column(db.String(50))
    工艺条件_设计温度 = db.Column(db.String(50))
    工艺条件_阀前压力 = db.Column(db.String(50))
    工艺条件_阀后压力 = db.Column(db.String(50))

    阀体_公称通径 = db.Column(db.String(50))
    阀体_连接方式及规格 = db.Column(db.String(100))
    阀体_材质 = db.Column(db.String(50))

    阀内件_阀座直径 = db.Column(db.String(50))
    阀内件_阀座序列号 = db.Column(db.String(50))
    阀内件_阀芯材质 = db.Column(db.String(50))
    阀内件_阀座材质 = db.Column(db.String(50))
    阀内件_阀杆材质 = db.Column(db.String(50))
    阀内件_流量特性 = db.Column(db.String(50))
    阀内件_泄露等级 = db.Column(db.String(50))
    阀内件_Cv值 = db.Column(db.String(50))

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

    手轮机构 = db.Column(db.String(50))
    设备编号 = db.Column(db.String(50))
    是否联锁 = db.Column(db.String(10))
    备注 = db.Column(db.Text)
