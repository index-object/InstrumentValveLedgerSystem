from app.devices import DeviceTypeRegistry, DeviceTypeConfig
from app.devices.types.pressure_transmitter import PressureTransmitter
from app.devices.types.local_pressure_gauge import LocalPressureGauge
from app.devices.types.temperature import Temperature
from app.devices.types.local_temperature import LocalTemperature
from app.devices.types.flow_meter import FlowMeter
from app.devices.types.level_transmitter import LevelTransmitter
from app.devices.types.local_level import LocalLevel
from app.devices.types.shaft_instrument import ShaftInstrument
from app.devices.types.control_valve import ControlValve
from app.devices.types.onoff_valve import OnOffValve


_field_groups_valve = [
    {
        "title": "基本信息",
        "fields": ["装置名称", "位号", "名称", "设备等级",
                   "型号规格", "生产厂家", "安装位置及用途"],
        "cols": 2,
    },
    {
        "title": "工艺条件",
        "fields": ["工艺条件_介质名称", "工艺条件_设计温度",
                   "工艺条件_阀前压力", "工艺条件_阀后压力"],
        "cols": 2,
    },
    {
        "title": "阀体",
        "fields": ["阀体_公称通径", "阀体_连接方式及规格",
                   "阀体_材质"],
        "cols": 2,
    },
    {
        "title": "阀内件",
        "fields": ["阀内件_阀座直径", "阀内件_阀座序列号",
                   "阀内件_阀芯材质", "阀内件_阀座材质",
                   "阀内件_阀杆材质", "阀内件_流量特性",
                   "阀内件_泄露等级", "阀内件_Cv值"],
        "cols": 2,
    },
    {
        "title": "执行机构",
        "fields": ["执行机构_形式", "执行机构_型号规格",
                   "执行机构_厂家", "执行机构_作用形式",
                   "执行机构_行程", "执行机构_弹簧范围",
                   "执行机构_气源压力", "执行机构_故障位置",
                   "执行机构_关阀时间", "执行机构_开阀时间"],
        "cols": 2,
    },
    {
        "title": "其他",
        "fields": ["手轮机构", "设备编号", "是否联锁", "备注"],
        "cols": 1,
    },
]

_filterable_fields_valve = [
    ("装置名称", "装置名称"), ("位号", "位号"),
    ("名称", "名称"), ("设备等级", "设备等级"),
    ("型号规格", "型号规格"), ("生产厂家", "生产厂家"),
    ("安装位置及用途", "安装位置及用途"), ("是否联锁", "是否联锁"),
]


def register_all():
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="control_valve", name="调节阀",
        model_class=ControlValve, icon="fa-valve",
        field_groups=_field_groups_valve,
        filterable_fields=_filterable_fields_valve,
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="onoff_valve", name="开关阀/切断阀",
        model_class=OnOffValve, icon="fa-valve",
        field_groups=_field_groups_valve,
        filterable_fields=_filterable_fields_valve,
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="pressure_transmitter", name="压力变送器",
        model_class=PressureTransmitter, icon="fa-tachometer-alt",
        field_groups=[
            {
                "title": "基本信息",
                "fields": ["装置名称", "位号", "安装位置及用途", "设备名称",
                          "设备等级", "规格型号", "生产厂家", "介质", "出厂编号"],
                "cols": 2,
            },
            {
                "title": "技术参数",
                "fields": ["测量范围", "连接方式及规格", "精度",
                          "电源", "输出信号", "是否联锁"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备等级", "设备等级"),
            ("规格型号", "规格型号"), ("生产厂家", "生产厂家"),
            ("介质", "介质"),
        ],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="local_pressure_gauge", name="就地压力表",
        model_class=LocalPressureGauge, icon="fa-gauge",
        field_groups=[
            {
                "title": "基本信息",
                "fields": ["装置名称", "位号", "安装位置及用途", "设备名称",
                          "设备等级", "规格型号", "生产厂家", "介质", "出厂编号"],
                "cols": 2,
            },
            {
                "title": "技术参数",
                "fields": ["测量范围", "连接方式及规格", "精度"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备等级", "设备等级"),
            ("规格型号", "规格型号"), ("生产厂家", "生产厂家"),
            ("介质", "介质"),
        ],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="temperature", name="温度仪表",
        model_class=Temperature, icon="fa-temperature-high",
        field_groups=[
            {
                "title": "基本信息",
                "fields": ["装置名称", "位号", "安装位置及用途", "设备名称",
                          "设备等级", "分度号", "规格型号", "生产厂家",
                          "介质", "出厂编号", "是否联锁"],
                "cols": 2,
            },
            {
                "title": "技术参数",
                "fields": ["测量范围", "插入深度", "连接方式及规格",
                          "精度", "套管规格及材质"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备等级", "设备等级"),
            ("分度号", "分度号"), ("生产厂家", "生产厂家"),
        ],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="local_temperature", name="就地温度计",
        model_class=LocalTemperature, icon="fa-thermometer-half",
        field_groups=[
            {
                "title": "基本信息",
                "fields": ["装置名称", "位号", "安装位置及用途", "设备名称",
                          "设备等级", "规格型号", "生产厂家", "介质", "出厂编号"],
                "cols": 2,
            },
            {
                "title": "技术参数",
                "fields": ["测量范围", "插入深度", "连接方式及规格",
                          "精度", "套管规格及材质"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备等级", "设备等级"),
        ],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="flow_meter", name="流量计",
        model_class=FlowMeter, icon="fa-water",
        field_groups=[
            {
                "title": "基本信息",
                "fields": ["装置名称", "位号", "安装位置及用途",
                          "设备名称", "设备等级", "规格型号", "生产厂家", "出厂编号"],
                "cols": 2,
            },
            {
                "title": "工艺参数",
                "fields": ["量程", "测量范围", "介质",
                          "设计温度", "设计压力"],
                "cols": 2,
            },
            {
                "title": "连接与信号",
                "fields": ["规格尺寸", "连接方式及规格", "电源",
                          "输出信号", "精度", "是否伴热", "是否联锁"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备等级", "设备等级"),
            ("规格型号", "规格型号"), ("生产厂家", "生产厂家"),
        ],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="level_transmitter", name="物位计",
        model_class=LevelTransmitter, icon="fa-chart-line",
        field_groups=[
            {
                "title": "基本信息",
                "fields": ["装置名称", "位号", "安装位置及用途",
                          "设备名称", "设备等级", "规格型号",
                          "生产厂家", "介质", "出厂编号", "是否联锁"],
                "cols": 2,
            },
            {
                "title": "技术参数",
                "fields": ["液位范围", "精度", "介质密度",
                          "电源", "输出信号", "连接方式及规格"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备等级", "设备等级"),
            ("生产厂家", "生产厂家"), ("介质", "介质"),
        ],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="local_level", name="就地液位计",
        model_class=LocalLevel, icon="fa-tint",
        field_groups=[
            {
                "title": "基本信息",
                "fields": ["装置名称", "位号", "安装位置及用途",
                          "设备名称", "设备等级", "规格型号",
                          "生产厂家", "介质", "出厂编号"],
                "cols": 2,
            },
            {
                "title": "技术参数",
                "fields": ["公称压力", "公称通径", "介质密度",
                          "液位范围", "精度", "连接方式及规格"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备等级", "设备等级"),
        ],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="shaft_instrument", name="机组轴系仪表",
        model_class=ShaftInstrument, icon="fa-cog",
        field_groups=[
            {
                "title": "基本信息",
                "fields": ["装置名称", "位号", "安装位置及用途",
                          "设备名称", "设备等级", "规格型号",
                          "生产厂家", "测量范围", "精度"],
                "cols": 2,
            },
            {
                "title": "联锁信息",
                "fields": ["是否联锁", "联锁设定值"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备等级", "设备等级"),
            ("生产厂家", "生产厂家"),
        ],
    ))
