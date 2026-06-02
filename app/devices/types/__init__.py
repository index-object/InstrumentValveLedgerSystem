from app.devices import DeviceTypeRegistry, DeviceTypeConfig
from app.devices.types.pressure_transmitter import PressureTransmitter
from app.devices.types.local_pressure_gauge import LocalPressureGauge
from app.devices.types.temperature import Temperature
from app.devices.types.local_temperature import LocalTemperature
from app.devices.types.flow_meter import FlowMeter
from app.devices.types.level_transmitter import LevelTransmitter
from app.devices.types.local_level import LocalLevel
from app.devices.types.shaft_instrument import ShaftInstrument


def register_all():
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="valve", name="阀门", model_class=None, icon="fa-valve",
        field_groups=[], filterable_fields=[],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="pressure_transmitter", name="压力变送器",
        model_class=PressureTransmitter, icon="fa-tachometer-alt",
        field_groups=[
            {
                "title": "基本信息",
                "fields": ["装置名称", "位号", "安装位置及用途", "设备名称",
                          "设备分级", "规格型号", "生产厂家", "介质", "编号"],
                "cols": 2,
            },
            {
                "title": "技术参数",
                "fields": ["测量范围Mpa", "连接方式及规格", "精度",
                          "电源", "输出信号", "是否联锁"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备分级", "设备分级"),
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
                          "设备分级", "规格型号", "生产厂家", "介质", "编号"],
                "cols": 2,
            },
            {
                "title": "技术参数",
                "fields": ["测量范围Mpa", "连接方式及规格", "精度"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备分级", "设备分级"),
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
                "fields": ["装置名称", "位号", "安装位置及用途", "设备介质",
                          "设备名称", "分级", "分度号", "规格型号",
                          "生产厂家", "出厂编号", "是否联锁"],
                "cols": 2,
            },
            {
                "title": "技术参数",
                "fields": ["测量范围(℃)", "插入深度(MM)", "连接方式及规格",
                          "精度", "法兰规格及材质"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("分级", "分级"),
            ("分度号", "分度号"), ("生产厂家", "生产厂家"),
        ],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="local_temperature", name="就地温度计",
        model_class=LocalTemperature, icon="fa-thermometer-half",
        field_groups=[
            {
                "title": "基本信息",
                "fields": ["装置名称", "位号", "安装位置及用途", "介质",
                          "设备名称", "设备分级", "规格型号",
                          "生产厂家", "出厂编号"],
                "cols": 2,
            },
            {
                "title": "技术参数",
                "fields": ["测量范围/℃", "插入深度/mm", "连接方式及规格",
                          "精度", "法兰规格及材质"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备分级", "设备分级"),
        ],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="flow_meter", name="流量计",
        model_class=FlowMeter, icon="fa-water",
        field_groups=[
            {
                "title": "基本信息",
                "fields": ["装置名称", "位号", "安装位置及用途",
                          "设备名称", "设备分级", "规格型号", "生产厂家", "编号"],
                "cols": 2,
            },
            {
                "title": "工艺参数",
                "fields": ["量程（kpa）", "测量范围", "工艺介质 / 介质 名称",
                          "设计 温度℃", "设计压力MPa"],
                "cols": 2,
            },
            {
                "title": "连接与信号",
                "fields": ["规格尺寸", "规格尺寸连接方式", "电源",
                          "输出信号", "精度", "是否伴热", "是否 联锁"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备分级", "设备分级"),
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
                          "设备名称", "设备分级", "规格型号",
                          "生产厂家", "介质", "出厂编号", "是否联锁"],
                "cols": 2,
            },
            {
                "title": "技术参数",
                "fields": ["液位范围/mm", "精度/mm", "密度g/cm3",
                          "电源", "输出信号", "连接方式及规格"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备分级", "设备分级"),
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
                          "设备名称", "设备分级", "规格型号",
                          "生产厂家", "介质", "出厂编号"],
                "cols": 2,
            },
            {
                "title": "技术参数",
                "fields": ["公称压力", "公称通径", "介质密度g/cm3",
                          "液位范围mm", "精度", "连接方式及规格"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备分级", "设备分级"),
        ],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="shaft_instrument", name="机组轴系仪表",
        model_class=ShaftInstrument, icon="fa-cog",
        field_groups=[
            {
                "title": "基本信息",
                "fields": ["装置名称", "位号", "安装位置及用途",
                          "设备名称", "设备分级", "规格型号",
                          "生产厂家", "测量范围", "精度"],
                "cols": 2,
            },
            {
                "title": "联锁信息",
                "fields": ["是否 联锁", "联锁 设定值"],
                "cols": 2,
            },
            {"title": "备注", "fields": ["备注"], "cols": 1},
        ],
        filterable_fields=[
            ("装置名称", "装置名称"), ("位号", "位号"),
            ("设备名称", "设备名称"), ("设备分级", "设备分级"),
            ("生产厂家", "生产厂家"),
        ],
    ))
