# Excel 批量导入功能设计文档

## 概述

实现从 Excel 文件批量导入台账数据的功能。上传的 Excel 每个 Sheet 对应一种设备类型，系统自动识别类型，未识别的由用户手动指定，最终导入到对应的数据库表中并自动创建台账合集（Ledger）。

## 流程

```
上传文件 → 安全解析Excel → 自动识别类型 → 弹窗处理未识别Sheet → 预览确认 → 执行导入
```

## 详细设计

### 1. 安全读取 Excel

示例文件包含 externalLinks，导致 openpyxl 读取时挂起。解决方案：

**读取流程：**
1. 将上传的 xlsx 作为 zip 打开
2. 复制到临时文件，排除 `xl/externalLinks/` 目录下的所有文件
3. 用 `openpyxl.load_workbook(tmp, read_only=True, data_only=True)` 读取
4. 读取完成后删除临时文件

**读取内容：**
- 所有 Sheet 名称
- 每个 Sheet 的列名（第一行 header）
- 每个 Sheet 的行数
- 每个 Sheet 的前 5 行样例数据

### 2. 类型自动识别

**匹配规则（按优先级）：**

1. `DeviceTypeRegistry.get(sheet_name)` — 直接以 code 匹配
2. `sheet_name == config.name` — 以展示名称匹配
3. 以上均不匹配 → 标记为"未识别"

**当前可自动识别的 Sheet：**
| Sheet 名 | 匹配类型 | 说明 |
|----------|---------|------|
| 流量计 | flow_meter | 名完全一致 |
| 物位计 | level_transmitter | 名完全一致 |
| 机组轴系仪表 | shaft_instrument | 名完全一致 |
| 就地压力表 | local_pressure_gauge | 名完全一致 |

**无法自动识别的 Sheet（需用户指定）：**
| Sheet 名 | 应映射类型 |
|----------|-----------|
| 截止阀 | valve |
| 球阀 | valve |
| 压力 | pressure_transmitter |
| 温度 | temperature |
| 就地温度 | local_temperature |
| 就地液位 | local_level |

### 3. 未识别类型弹窗

上传解析完成后，若有未识别的 Sheet，弹出模态对话框：

- 逐行显示未识别的 Sheet 名称
- 每行一个下拉选择框，选项为所有设备类型 + "跳过"
- 用户为每个 Sheet 选择映射类型
- 点击确认后进入预览页

### 4. 预览页

展示内容：
- 每个 Sheet 的：名称、识别/选择的类型、行数、Column 列表、前 3 行样例数据
- 同类型多 Sheet 的合并选项：每个 Sheet 旁有一个"合并到同一台账合集"复选框
  - 选中合并的 Sheet 共享同一个 Ledger 名称（取第一个 Sheet 的名称）
  - 未选中的每个 Sheet 独立创建 Ledger
- 确认导入按钮

### 5. 执行导入

每个 Sheet 的处理步骤：

1. **查找或创建 Ledger：**
   - 按 `名称 + 类型` 查找已有 Ledger
   - 不存在则新建：`Ledger(名称=sheet_name, 类型=type_code, created_by=current_user)`
   - 若合并，多个 Sheet 共享同一 Ledger

2. **逐行创建记录：**
   - 实例化对应 model_class
   - 遍历 Excel 列名，若有同名属性则赋值，否则忽略
   - 设置 `ledger_id`、`created_by`、`status="draft"`
   - 逐行添加，不中断整体流程

3. **事务控制：**
   - 每个 Sheet 独立事务
   - 某行失败不影响其他行

### 6. 现有代码改动点

**`app/routes/imports.py`：**
- `upload()` — 改为返回 JSON 给前端弹窗处理，而非直接渲染预览
- 新增 `/imports/match` (POST) — 接收前端提交的 Sheet→类型映射关系
- `/imports/execute` — 接收映射关系和合并选项

**前端改动：**
- 上传成功后，若有未识别 Sheet → 弹窗选择类型
- 显示预览页面，增加合并选项
- 确认导入按钮提交映射 + 合并配置

**新增工具函数：**
- `app/utils/importer.py` — `safe_read_excel()` 安全读取，Excel 数据解析

## 不做的事项

- 列名别名映射（列名必须与模型字段一致，不一致则字段留空）
- 导入历史日志
- 实时进度条
- 失败重试
- 数据校验（位号唯一性等依赖现有数据库约束）
