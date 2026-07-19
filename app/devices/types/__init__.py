import os

import yaml

from app.devices import DeviceTypeRegistry, DeviceTypeConfig
from app.devices.types.pressure_transmitter import PressureTransmitter
from app.devices.types.local_pressure_gauge import LocalPressureGauge
from app.devices.types.temperature import Temperature
from app.devices.types.local_temperature import LocalTemperature
from app.devices.types.flow_meter import FlowMeter
from app.devices.types.level_transmitter import LevelTransmitter
from app.devices.types.local_level import LocalLevel
from app.devices.types.control_valve import ControlValve
from app.devices.types.onoff_valve import OnOffValve
from app.devices.types.electric_valve import ElectricValve


def _load_type_config():
    """从 types.yaml 加载类型名称，返回 {code: name} 映射"""
    yaml_path = os.path.join(os.path.dirname(__file__), '..', '..', 'import_engine', 'config', 'types.yaml')
    names = {}
    try:
        with open(yaml_path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        for entry in data.get('types', {}).values():
            code = entry.get('code')
            name = entry.get('name')
            if code and name and code not in names:
                names[code] = name
    except Exception:
        pass
    return names


_type_names = _load_type_config()


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

_field_groups_electric_valve = [
    {
        "title": "基本信息",
        "fields": ["装置名称", "位号", "名称", "安装位置及用途",
                   "设备等级", "型号规格", "生产厂家", "设备编号"],
        "cols": 2,
    },
    {
        "title": "工艺参数",
        "fields": ["介质名称", "设计温度℃", "操作压力",
                   "设计压力", "公称通径"],
        "cols": 2,
    },
    {
        "title": "阀体参数",
        "fields": ["阀体", "阀体材质", "阀座材质", "阀芯材质"],
        "cols": 2,
    },
    {
        "title": "流量特性",
        "fields": ["流量特性", "泄露等级"],
        "cols": 2,
    },
    {
        "title": "电气参数",
        "fields": ["转矩Nm", "功率", "转速r_per_min", "转圈数r",
                   "电源", "防护等级"],
        "cols": 2,
    },
    {
        "title": "执行机构",
        "fields": ["作用形式", "额定行程"],
        "cols": 2,
    },
    {
        "title": "其他",
        "fields": ["是否联锁", "备注"],
        "cols": 1,
    },
]

_filterable_fields_electric_valve = [
    ("装置名称", "装置名称"), ("位号", "位号"),
    ("名称", "名称"), ("设备等级", "设备等级"),
    ("型号规格", "型号规格"), ("生产厂家", "生产厂家"),
    ("安装位置及用途", "安装位置及用途"),
    ("是否联锁", "是否联锁"),
]


def register_all():
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="control_valve", name=_type_names.get("control_valve", "调节阀"),
        model_class=ControlValve, icon="fa-valve",
        field_groups=_field_groups_valve,
        filterable_fields=_filterable_fields_valve,
        color_scheme=['#d1fae5','#a7f3d0','#065f46','#6ee7b7'],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="onoff_valve", name=_type_names.get("onoff_valve", "开关阀/切断阀"),
        model_class=OnOffValve, icon="fa-valve",
        field_groups=_field_groups_valve,
        filterable_fields=_filterable_fields_valve,
        color_scheme=['#d1fae5','#a7f3d0','#065f46','#6ee7b7'],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="electric_valve", name=_type_names.get("electric_valve", "电动阀"),
        model_class=ElectricValve, icon="fa-bolt",
        field_groups=_field_groups_electric_valve,
        filterable_fields=_filterable_fields_electric_valve,
        color_scheme=['#fef3c7','#fde68a','#92400e','#fcd34d'],
    ))
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="pressure_transmitter", name=_type_names.get("pressure_transmitter", "远传压力"),
        model_class=PressureTransmitter, icon="fa-tachometer-alt",
        color_scheme=['#dbeafe','#bfdbfe','#1e40af','#93c5fd'],
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
        code="local_pressure_gauge", name=_type_names.get("local_pressure_gauge", "就地压力表"),
        model_class=LocalPressureGauge, icon="fa-gauge",
        color_scheme=['#fef3c7','#fde68a','#92400e','#fcd34d'],
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
        code="temperature", name=_type_names.get("temperature", "远传温度"),
        model_class=Temperature, icon="fa-temperature-high",
        color_scheme=['#fee2e2','#fecaca','#991b1b','#fca5a5'],
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
        code="local_temperature", name=_type_names.get("local_temperature", "就地温度计"),
        model_class=LocalTemperature, icon="fa-thermometer-half",
        color_scheme=['#fce7f3','#fbcfe8','#9d174d','#f9a8d4'],
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
        code="flow_meter", name=_type_names.get("flow_meter", "流量计"),
        model_class=FlowMeter, icon="fa-water",
        color_scheme=['#e0e7ff','#c7d2fe','#4338ca','#a5b4fc'],
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
        code="level_transmitter", name=_type_names.get("level_transmitter", "远传液位"),
        model_class=LevelTransmitter, icon="fa-chart-line",
        color_scheme=['#ccfbf1','#99f6e4','#115e59','#5eead4'],
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
        code="local_level", name=_type_names.get("local_level", "就地液位计"),
        model_class=LocalLevel, icon="fa-tint",
        color_scheme=['#ffedd5','#fed7aa','#9a3412','#fdba74'],
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

