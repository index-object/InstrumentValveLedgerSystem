"""
导入数据处理模块 - 数据清洗与格式对齐

处理组合行结构的Excel文件：
- 阀门主行：第0列（序号）有值
- 附件行：第0列为空，第3列（名称）有值
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional
import pandas as pd


class RowType(Enum):
    """行类型枚举"""
    VALVE = "valve"        # 阀门主行
    ATTACHMENT = "attachment"  # 附件行
    EMPTY = "empty"        # 空行


@dataclass
class ImportResult:
    """导入结果"""
    valve_groups: List["ValveGroup"] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ValveGroup:
    """阀门组：一个阀门主行 + 若干附件行"""
    valve_data: dict
    attachments: List[dict] = field(default_factory=list)
    row_number: int = 0


# 阀门主行列索引映射（基于实际数据验证）
VALVE_COLUMN_MAP = {
    1: "装置名称",
    2: "位号",
    3: "名称",
    4: "设备等级",
    5: "型号规格",
    6: "生产厂家",
    7: "安装位置及用途",
    8: "工艺条件_介质名称",
    9: "工艺条件_设计温度",
    10: "工艺条件_阀前压力",
    11: "工艺条件_阀后压力",
    12: "阀内件_阀座直径",
    13: "阀体_公称通径",
    14: "阀体_连接方式及规格",
    15: "阀体_材质",
    16: "阀内件_阀座序列号",
    17: "阀内件_阀芯材质",
    18: "阀内件_阀座材质",
    19: "阀内件_阀杆材质",
    20: "阀内件_流量特性",
    21: "阀内件_泄露等级",
    22: "阀内件_Cv值",
    23: "执行机构_形式",
    24: "执行机构_型号规格",
    25: "执行机构_厂家",
    26: "执行机构_作用形式",
    27: "执行机构_行程",
    28: "执行机构_弹簧范围",
    29: "执行机构_气源压力",
    30: "执行机构_故障位置",
    31: "执行机构_关阀时间",
    32: "执行机构_开阀时间",
    33: "设备编号",
    34: "是否联锁",
    35: "备注",
}

# 附件行列索引映射
ATTACHMENT_COLUMN_MAP = {
    3: "名称",      # 附件类型（定位器、电磁阀等）
    5: "型号规格",
    6: "生产厂家",
}


class ImportDataProcessor:
    """导入数据处理器"""

    # 空值标识符
    EMPTY_MARKERS = {"-", "/", "\\", "无", "NA", "N/A", ""}

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def process_file(self, file) -> ImportResult:
        """
        处理上传文件，返回解析结果

        Args:
            file: 上传的文件对象

        Returns:
            ImportResult: 包含阀门组和错误信息的结果对象
        """
        try:
            # 读取Excel，跳过前两行标题
            df = pd.read_excel(file, header=None, skiprows=2)
            return self.parse_excel(df)
        except Exception as e:
            result = ImportResult()
            result.errors.append(f"文件读取失败: {str(e)}")
            return result

    def parse_excel(self, df: pd.DataFrame) -> ImportResult:
        """
        解析Excel，返回阀门组列表

        Args:
            df: pandas DataFrame（无标题行，从第3行开始）

        Returns:
            ImportResult: 包含阀门组和错误信息的结果对象
        """
        result = ImportResult()

        current_valve: Optional[ValveGroup] = None
        row_number = 3  # 从第3行开始（跳过两行标题）

        for _, row in df.iterrows():
            row_type = self.identify_row_type(row)

            if row_type == RowType.VALVE:
                # 保存之前的阀门组
                if current_valve and current_valve.valve_data.get("位号"):
                    result.valve_groups.append(current_valve)

                # 开始新的阀门组
                valve_data = self.extract_valve_data(row)
                current_valve = ValveGroup(
                    valve_data=valve_data,
                    row_number=row_number
                )

                # 检查位号是否为空
                if not valve_data.get("位号"):
                    result.errors.append(
                        f"第{row_number}行：阀门主行位号为空，已跳过"
                    )
                    current_valve = None

            elif row_type == RowType.ATTACHMENT:
                if current_valve is None:
                    result.warnings.append(
                        f"第{row_number}行：附件行无关联阀门，已跳过"
                    )
                else:
                    attachment_data = self.extract_attachment_data(
                        row, current_valve.valve_data.get("设备等级")
                    )
                    current_valve.attachments.append(attachment_data)

            # 空行：跳过

            row_number += 1

        # 保存最后一个阀门组
        if current_valve and current_valve.valve_data.get("位号"):
            result.valve_groups.append(current_valve)

        result.errors.extend(self.errors)
        result.warnings.extend(self.warnings)

        return result

    def identify_row_type(self, row: pd.Series) -> RowType:
        """
        识别行类型：阀门主行/附件行/空行

        Args:
            row: pandas Series 表示一行数据

        Returns:
            RowType: 行类型枚举值
        """
        # 获取关键列的值
        col0 = self._get_cell_value(row, 0)  # 序号
        col3 = self._get_cell_value(row, 3)  # 名称

        # 第0列（序号）有值 -> 阀门主行
        if col0 and str(col0).strip():
            return RowType.VALVE

        # 第0列为空，第3列（名称）有值 -> 附件行
        if col3 and str(col3).strip():
            return RowType.ATTACHMENT

        # 其他情况 -> 空行
        return RowType.EMPTY

    def extract_valve_data(self, row: pd.Series) -> dict:
        """
        从阀门主行提取数据

        Args:
            row: pandas Series 表示一行数据

        Returns:
            dict: 阀门数据字典
        """
        data = {}
        for col_idx, field_name in VALVE_COLUMN_MAP.items():
            value = self._get_cell_value(row, col_idx)
            cleaned = self.clean_value(value, field_name)
            if cleaned is not None:
                data[field_name] = cleaned
        return data

    def extract_attachment_data(
        self,
        row: pd.Series,
        valve_device_grade: Optional[str] = None
    ) -> dict:
        """
        从附件行提取数据

        Args:
            row: pandas Series 表示一行数据
            valve_device_grade: 所属阀门的设备等级（自动继承）

        Returns:
            dict: 附件数据字典
        """
        data = {}

        # 从Excel提取的字段
        for col_idx, field_name in ATTACHMENT_COLUMN_MAP.items():
            value = self._get_cell_value(row, col_idx)
            cleaned = self.clean_value(value, field_name)
            if cleaned is not None:
                data[field_name] = cleaned

        # 附件类型（从名称列推断）
        name = data.get("名称", "")
        if name:
            data["type"] = self._infer_attachment_type(name)

        # 继承阀门的设备等级
        if valve_device_grade:
            data["设备等级"] = valve_device_grade

        return data

    def clean_value(self, value: Any, field_name: str) -> Optional[str]:
        """
        数据清洗：去除空白、格式标准化

        Args:
            value: 原始值
            field_name: 字段名（用于特殊处理）

        Returns:
            Optional[str]: 清洗后的字符串，或 None
        """
        if value is None:
            return None

        # 处理 NaN
        if pd.isna(value):
            return None

        # 转为字符串并去除首尾空白
        s = str(value).strip()

        # 空字符串
        if not s:
            return None

        # 空值标记
        if s in self.EMPTY_MARKERS:
            return None

        return s

    def _get_cell_value(self, row: pd.Series, col_idx: int) -> Any:
        """安全获取单元格值"""
        try:
            if col_idx < len(row):
                value = row.iloc[col_idx]
                # 处理 NaN 值
                if pd.isna(value):
                    return None
                return value
        except Exception:
            pass
        return None

    def _infer_attachment_type(self, name: str) -> str:
        """
        根据附件名称推断类型

        Args:
            name: 附件名称

        Returns:
            str: 附件类型
        """
        name_lower = name.lower()

        type_keywords = {
            "定位器": ["定位器", "positioner"],
            "电磁阀": ["电磁阀", "solenoid"],
            "过滤器": ["过滤器", "filter"],
            "减压阀": ["减压阀", "regulator"],
            "保位阀": ["保位阀", "lock-up"],
            "放大器": ["放大器", "amplifier"],
            "转换器": ["转换器", "converter"],
            "限位开关": ["限位开关", "switch"],
            "位置变送器": ["位置变送器", "transmitter"],
        }

        for att_type, keywords in type_keywords.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return att_type

        # 默认使用原始名称
        return name


def process_import_preview(
    file,
    existing_valves: Optional[dict] = None
) -> dict:
    """
    处理导入预览

    Args:
        file: 上传的文件对象
        existing_valves: 现有阀门字典 {位号: valve_id}

    Returns:
        dict: 包含预览数据的字典
    """
    processor = ImportDataProcessor()
    result = processor.process_file(file)

    conflicts = []
    new_records = []

    existing_valves = existing_valves or {}

    for group in result.valve_groups:
        tag_number = group.valve_data.get("位号", "")

        if tag_number in existing_valves:
            conflicts.append({
                "位号": tag_number,
                "existing_id": existing_valves[tag_number],
                "valve_data": group.valve_data,
                "attachments": group.attachments,
                "row_number": group.row_number,
            })
        else:
            new_records.append({
                "valve_data": group.valve_data,
                "attachments": group.attachments,
                "row_number": group.row_number,
            })

    return {
        "conflicts": conflicts,
        "new_records": new_records,
        "errors": result.errors,
        "warnings": result.warnings,
        "total": len(result.valve_groups),
    }