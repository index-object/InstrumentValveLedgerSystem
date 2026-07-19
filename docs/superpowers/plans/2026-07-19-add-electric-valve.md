# 电动阀新增 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) for syntax tracking.

**Goal:** 在现有仪表阀门台账系统中新增"电动阀"设备类型，使其拥有完整的增删改查、导入导出、审批流程和前端显示能力。

**Architecture:** ElectricValve 继承 ValveBase（复用公共字段），追加 6 个专属字段（转矩Nm、功率、转速r/min、转圈数r、电源、防护等级）。通过 DeviceTypeRegistry 注册机制自动接入 CRUD 路由和审批流。导入引擎通过 types.yaml 配置 + synonyms.yaml 同义词覆盖三个来源文件（储运中心/动力中心/低位热）。模板通过 VALVE_TYPES 条件分支区分显示。

**Tech Stack:** Flask + SQLAlchemy + Jinja2 + YAML config

---

## 文件变更清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `app/devices/types/electric_valve.py` | **新建** | ElectricValve 模型类 |
| `app/devices/types/__init__.py` | 修改 | 导入 + 注册 + field_groups |
| `app/devices/valve_helper.py` | 修改 | VALVE_TYPES 列表追加 |
| `app/import_engine/config/types.yaml` | 修改 | 电动阀类型配置 + column_mapping |
| `app/import_engine/config/synonyms.yaml` | 修改 | 电动阀列名同义词 |
| `app/import_engine/engine.py` | 修改 | model_map 注册 + 导入 |
| `app/__init__.py` | 修改 | context_processor 注入 VALVE_TYPES |
| `templates/valves/form.html` | 修改 | 电动阀专属表单项（6步） |
| `templates/valves/detail.html` | 修改 | 电动阀详情显示块 |
| `templates/valves/list.html` | 修改 | 列头 + 数据行 + URL 条件 |
| `templates/maintenance/list.html` | 修改 | URL 条件 |

---

### Task 1: 创建 ElectricValve 模型类

**Files:**
- Create: `app/devices/types/electric_valve.py`

- [ ] **Step 1: 创建模型文件**

```python
from app.devices.types.valve_base import ValveBase, db


class ElectricValve(ValveBase):
    __tablename__ = "electric_valves"

    转矩Nm = db.Column(db.String(50))
    功率 = db.Column(db.String(50))
    转速r_per_min = db.Column("转速r/min", db.String(50))
    转圈数r = db.Column(db.String(50))
    电源 = db.Column(db.String(50))
    防护等级 = db.Column(db.String(50))
```

注意：`转速r/min` 列名包含特殊字符 `/`，SQLAlchemy 不能直接用作属性名，所以用 `转速r_per_min` 作为属性名，通过第一个参数指定实际列名 `转速r/min`。

- [ ] **Step 2: 验证文件创建**

Run: `python -c "from app.devices.types.electric_valve import ElectricValve; print(ElectricValve.__tablename__)"`
Expected: `electric_valves`

---

### Task 2: 在 DeviceTypeRegistry 中注册电动阀

**Files:**
- Modify: `app/devices/types/__init__.py`

- [ ] **Step 1: 追加导入和 field_groups 定义**

在文件顶部导入区追加：
```python
from app.devices.types.electric_valve import ElectricValve
```

在 `_filterable_fields_valve` 定义之后、`register_all()` 之前追加电动阀专属 field_groups：

```python
_field_groups_electric_valve = [
    {
        "title": "基本信息",
        "fields": ["装置名称", "位号", "名称", "设备等级",
                   "型号规格", "生产厂家", "安装位置及用途"],
        "cols": 2,
    },
    {
        "title": "工艺条件",
        "fields": ["工艺条件_介质名称", "工艺条件_设计温度"],
        "cols": 2,
    },
    {
        "title": "阀体",
        "fields": ["阀体_公称通径", "阀体_材质"],
        "cols": 2,
    },
    {
        "title": "阀内件",
        "fields": ["阀内件_阀芯材质", "阀内件_阀座材质",
                   "阀内件_流量特性", "阀内件_泄露等级"],
        "cols": 2,
    },
    {
        "title": "电气参数",
        "fields": ["转矩Nm", "功率", "转速r/min", "转圈数r",
                   "电源", "防护等级"],
        "cols": 2,
    },
    {
        "title": "其他",
        "fields": ["设备编号", "是否联锁", "备注"],
        "cols": 1,
    },
]

_filterable_fields_electric_valve = [
    ("装置名称", "装置名称"), ("位号", "位号"),
    ("名称", "名称"), ("设备等级", "设备等级"),
    ("型号规格", "型号规格"), ("生产厂家", "生产厂家"),
    ("安装位置及用途", "安装位置及用途"), ("是否联锁", "是否联锁"),
    ("转矩Nm", "转矩Nm"), ("功率", "功率"),
    ("转速r/min", "转速r/min"), ("电源", "电源"),
    ("防护等级", "防护等级"),
]
```

- [ ] **Step 2: 在 register_all() 中追加**

在 `onoff_valve` 注册之后追加：
```python
    DeviceTypeRegistry.register(DeviceTypeConfig(
        code="electric_valve", name=_type_names.get("electric_valve", "电动阀"),
        model_class=ElectricValve, icon="fa-bolt",
        field_groups=_field_groups_electric_valve,
        filterable_fields=_filterable_fields_electric_valve,
        color_scheme=['#fef3c7','#fde68a','#92400e','#fcd34d'],
    ))
```

注意 register_all() 中其他非阀门类型的注册不需要修改。

- [ ] **Step 3: 验证注册**

Run: `python -c "from app.devices.types import register_all; from app.devices import DeviceTypeRegistry; register_all(); c = DeviceTypeRegistry.get('electric_valve'); print(c.code, c.name, c.model_class.__name__)"`
Expected: `electric_valve 电动阀 ElectricValve`

---

### Task 3: 更新 VALVE_TYPES 列表

**Files:**
- Modify: `app/devices/valve_helper.py`

- [ ] **Step 1: 追加类型编码**

```python
VALVE_TYPES = ["control_valve", "onoff_valve", "electric_valve"]
```

- [ ] **Step 2: 验证**

Run: `python -c "from app.devices.valve_helper import VALVE_TYPES; print(VALVE_TYPES)"`
Expected: `['control_valve', 'onoff_valve', 'electric_valve']`

---

### Task 4: 导入引擎 types.yaml 配置

**Files:**
- Modify: `app/import_engine/config/types.yaml`

- [ ] **Step 1: 追加电动阀类型配置**

在 `onoff_valve` 段落之后追加：

```yaml
  electric_valve:
    code: electric_valve
    name: 电动阀
    model_class: ElectricValve
    sheet_keywords: ["电动阀", "消防电动阀"]
    column_signatures: ["控制转矩Nm", "转矩Nm", "输出转矩Nm", "功率KW", "转圈数r", "防护等级"]
    column_mapping:
      装置名称: 装置名称
      位号: 位号
      设备名称: 名称
      设备等级: 设备等级
      设备分级: 设备等级
      分级: 设备等级
      型号规格: 型号规格
      规格型号: 型号规格
      生产厂家: 生产厂家
      厂家: 生产厂家
      安装位置及用途: 安装位置及用途
      介质名称: 工艺条件_介质名称
      液体名称: 工艺条件_介质名称
      设计温度℃: 工艺条件_设计温度
      设计温度: 工艺条件_设计温度
      阀体: 阀体_材质
      阀体材质: 阀体_材质
      公称通径: 阀体_公称通径
      操作压力: 工艺条件_阀前压力
      设计压力: 工艺条件_阀后压力
      阀芯材质: 阀内件_阀芯材质
      阀座材质: 阀内件_阀座材质
      流量特性: 阀内件_流量特性
      泄露等级: 阀内件_泄露等级
      泄漏等级: 阀内件_泄露等级
      作用形式: 执行机构_作用形式
      额定行程: 执行机构_行程
      控制转矩Nm: 转矩Nm
      输出转矩Nm: 转矩Nm
      转矩Nm: 转矩Nm
      功率KW: 功率
      功率（w）: 功率
      功率: 功率
      转速r/min: 转速r/min
      转速rmin: 转速r/min
      转圈数r: 转圈数r
      电源: 电源
      防护等级: 防护等级
      生产编号: 设备编号
      设备编号: 设备编号
      出厂编号: 设备编号
      是否联锁: 是否联锁
      备注: 备注
```

此 column_mapping 覆盖三个来源文件的所有列名变体。synonyms.yaml 负责将 Excel 列名标准化，column_mapping 将标准化列名映射到模型属性。

- [ ] **Step 2: 验证 YAML 语法**

Run: `python -c "import yaml; yaml.safe_load(open('app/import_engine/config/types.yaml')); print('OK')"`
Expected: `OK`

---

### Task 5: 追加同义词映射

**Files:**
- Modify: `app/import_engine/config/synonyms.yaml`

- [ ] **Step 1: 追加电动阀相关同义词**

在文件末尾追加：

```yaml
  控制转矩Nm: ["控制转矩Nm", "输出转矩Nm", "转矩Nm"]
  功率KW: ["功率KW", "功率（w）", "功率"]
  转速r/min: ["转速r/min", "转速rmin"]
  转圈数r: ["转圈数r"]
  防护等级: ["防护等级"]
```

---

### Task 6: 导入引擎 engine.py 注册模型

**Files:**
- Modify: `app/import_engine/engine.py`

- [ ] **Step 1: 追加导入**

在顶部 `from app.devices.types.onoff_valve import OnOffValve` 之后追加：
```python
from app.devices.types.electric_valve import ElectricValve
```

- [ ] **Step 2: 追加 model_map 和 preserve 列表**

在 `_get_model_class()` 方法的 `model_map` 字典中追加：
```python
                "ElectricValve": ElectricValve,
```

在 `_process_sheet()` 方法中修改 preserve 行（约第 196 行）：
```python
        preserve = model_cls in (ControlValve, OnOffValve, ElectricValve)
```

`preserve=True` 确保导入时按源数据顺序创建记录，对阀门类型有意义。

---

### Task 7: 注入 VALVE_TYPES 到模板上下文

**Files:**
- Modify: `app/__init__.py`

- [ ] **Step 1: 在 context_processor 中注入**

找到 `inject_pending_count` 函数，在其返回字典中追加：

```python
    from app.devices.valve_helper import VALVE_TYPES
    # ... 在 return 字典中追加
    return dict(
        pending_count=pending_count,
        VALVE_TYPES=VALVE_TYPES,
    )
```

具体修改：在文件顶部已有 `from app.devices.valve_helper import get_all_valve_models`，追加 `VALVE_TYPES` 导入。在 `inject_pending_count` 函数的 `return` 语句中添加 `VALVE_TYPES=VALVE_TYPES`。

---

### Task 8: 修改表单模板 form.html

**Files:**
- Modify: `templates/valves/form.html`

- [ ] **Step 1: 修改步骤条，将电动阀专属步骤替换第5步**

将第 45-56 行的步骤条改为根据类型动态显示。整体将 `<div class="step-wizard">` 内的 `.step-item` 包裹在循环或条件中。具体修改：

在 `form.html` 中，步骤条的第5步原来是"执行机构"，需要根据类型切换：

```html
<div class="step-item" data-step="5" onclick="goToStep(5)">
    <div class="step-number">5</div>
    <div class="step-label">{% if ledger and ledger.类型 == 'electric_valve' %}电气参数{% else %}执行机构{% endif %}</div>
</div>
```

- [ ] **Step 2: 将第5步表单项改为条件渲染**

将原有第5步 `<div class="form-step" data-step="5">` 的全部内容改为条件分支：

```html
    {% if ledger and ledger.类型 == 'electric_valve' %}
    <div class="form-step" data-step="5">
        <div class="cmp-form-section" id="electrical-params">
            <div class="cmp-form-section__header" style="background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);">
                <i class="bi bi-lightning-charge-fill"></i>
                <h5>电气参数</h5>
            </div>
            <div class="cmp-form-section__body">
                <div class="cmp-field-row">
                    <div class="cmp-field">
                        <label class="cmp-label"><i class="bi bi-speedometer2" style="color: var(--text-muted);"></i> 转矩(Nm)</label>
                        <input type="text" name="转矩Nm" class="form-control cmp-input" value="{{ valve.转矩Nm or '' }}" placeholder="如：100Nm">
                    </div>
                    <div class="cmp-field">
                        <label class="cmp-label"><i class="bi bi-lightning" style="color: var(--text-muted);"></i> 功率</label>
                        <input type="text" name="功率" class="form-control cmp-input" value="{{ valve.功率 or '' }}" placeholder="如：0.37KW">
                    </div>
                    <div class="cmp-field">
                        <label class="cmp-label"><i class="bi bi-arrow-repeat" style="color: var(--text-muted);"></i> 转速(r/min)</label>
                        <input type="text" name="转速r/min" class="form-control cmp-input" value="{{ valve.转速r/min or '' }}" placeholder="如：24r/min">
                    </div>
                </div>
                <div class="cmp-field-row">
                    <div class="cmp-field">
                        <label class="cmp-label"><i class="bi bi-arrow-counterclockwise" style="color: var(--text-muted);"></i> 转圈数(r)</label>
                        <input type="text" name="转圈数r" class="form-control cmp-input" value="{{ valve.转圈数r or '' }}" placeholder="如：15r">
                    </div>
                    <div class="cmp-field">
                        <label class="cmp-label"><i class="bi bi-plug" style="color: var(--text-muted);"></i> 电源</label>
                        <input type="text" name="电源" class="form-control cmp-input" value="{{ valve.电源 or '' }}" placeholder="如：380V/3相/50Hz">
                    </div>
                    <div class="cmp-field">
                        <label class="cmp-label"><i class="bi bi-shield-check" style="color: var(--text-muted);"></i> 防护等级</label>
                        <input type="text" name="防护等级" class="form-control cmp-input" value="{{ valve.防护等级 or '' }}" placeholder="如：IP65">
                    </div>
                </div>
            </div>
        </div>
        <div class="step-actions">
            <button type="button" class="cmp-btn cmp-btn--secondary" onclick="goToStep(4)">
                <i class="bi bi-arrow-left"></i> 上一步
            </button>
            <button type="button" class="cmp-btn cmp-btn--primary" onclick="goToStep(6)">
                下一步 <i class="bi bi-arrow-right"></i>
            </button>
        </div>
    </div>
    {% else %}
    {# 原气动执行机构步骤 - 保持不动 #}
    <div class="form-step" data-step="5">
        ...（原第5步全部内容）...
    </div>
    {% endif %}
```

- [ ] **Step 3: 修改第4步（阀内件）去掉不适用的字段（非电动阀类型保持原样）**

在阀内件表单中，如果类型是 electric_valve，则只显示阀芯材质、阀座材质、流量特性、泄露等级；隐藏阀座直径、阀杆材质、Cv 值。

```html
                <div class="cmp-field-row">
                    {% if not (ledger and ledger.类型 == 'electric_valve') %}
                    <div class="cmp-field">
                        <label class="cmp-label"><i class="bi bi-circle" style="color: var(--text-muted);"></i> 阀座直径</label>
                        <input type="text" name="阀内件_阀座直径" class="form-control cmp-input" value="{{ valve.阀内件_阀座直径 or '' }}" placeholder="请输入阀座直径">
                    </div>
                    {% endif %}
                    <!-- 其他字段不变 -->
```

- [ ] **Step 4: 附件模板的附件类型下拉增加电动阀选项**

在 `<template id="attachment-row-template">` 中的 `<select name="attachment_type">` 内追加：
```html
                    <option value="电动机">电动机</option>
                    <option value="减速机构">减速机构</option>
```

---

### Task 9: 修改详情模板 detail.html

**Files:**
- Modify: `templates/valves/detail.html`

- [ ] **Step 1: 在详情页中追加电动阀电气参数显示块**

在"阀体信息"下方、"执行机构"上方插入条件块：

```html
                    {% if valve.转矩Nm or valve.功率 or valve.转速r/min or valve.转圈数r or valve.电源 or valve.防护等级 %}
                    <div class="cmp-detail-info-section">
                        <div class="cmp-detail-info-section__header" style="background: linear-gradient(135deg, #f59e0b, #fbbf24); color: white;">
                            <i class="bi bi-lightning-charge-fill"></i>
                            <span>电气参数</span>
                            <span class="section-count">6项</span>
                        </div>
                        <div class="cmp-detail-info-section__body">
                            <div class="cmp-detail-info-row">
                                <span class="cmp-detail-info-label"><i class="bi bi-speedometer2"></i> 转矩(Nm)</span>
                                <span class="cmp-detail-info-value">{{ valve.转矩Nm or '-' }}</span>
                            </div>
                            <div class="cmp-detail-info-row">
                                <span class="cmp-detail-info-label"><i class="bi bi-lightning"></i> 功率</span>
                                <span class="cmp-detail-info-value">{{ valve.功率 or '-' }}</span>
                            </div>
                            <div class="cmp-detail-info-row">
                                <span class="cmp-detail-info-label"><i class="bi bi-arrow-repeat"></i> 转速(r/min)</span>
                                <span class="cmp-detail-info-value">{{ valve.转速r/min or '-' }}</span>
                            </div>
                            <div class="cmp-detail-info-row">
                                <span class="cmp-detail-info-label"><i class="bi bi-arrow-counterclockwise"></i> 转圈数(r)</span>
                                <span class="cmp-detail-info-value">{{ valve.转圈数r or '-' }}</span>
                            </div>
                            <div class="cmp-detail-info-row">
                                <span class="cmp-detail-info-label"><i class="bi bi-plug"></i> 电源</span>
                                <span class="cmp-detail-info-value">{{ valve.电源 or '-' }}</span>
                            </div>
                            <div class="cmp-detail-info-row">
                                <span class="cmp-detail-info-label"><i class="bi bi-shield-check"></i> 防护等级</span>
                                <span class="cmp-detail-info-value">{{ valve.防护等级 or '-' }}</span>
                            </div>
                        </div>
                    </div>
                    {% endif %}
```

- [ ] **Step 2: 修改"执行机构"显示块，判断阀门类型**

将原有执行机构块用条件包起来：
```html
                    {% if not (valve.转矩Nm is defined and (valve.转矩Nm or valve.功率 or valve.转速r/min or valve.转圈数r or valve.电源 or valve.防护等级)) %}
                    <div class="cmp-detail-info-section">
                        ...
                    </div>
                    {% endif %}
```

更准确的判断：如果阀门是 ElectricValve 实例，则隐藏执行机构块。但 Jinja2 模板无法直接判断 Python 类型。改用检查 ElectricValve 特有字段存在与否来判断：

```html
                    {% if not (valve.转矩Nm is defined) %}
                    <div class="cmp-detail-info-section">
                        <div class="cmp-detail-info-section__header cmp-detail-info-section__header--green">
                            <i class="bi bi-lightning-charge"></i>
                            <span>执行机构</span>
                            <span class="section-count">10项</span>
                        </div>
                        ...
                    </div>
                    {% endif %}
```

注：`valve.转矩Nm is defined` 在 Jinja2 中对所有对象属性均为 True（因为 Python 属性总是存在），所以这个判断不生效。

替代方案：从视图函数传递 `valve_type` 参数：

```python
# 在 ledgers.py valve_detail 视图函数中
return render_template(
    "valves/detail.html",
    valve=valve,
    ledger_id=ledger_id,
    from_param=from_param,
    valve_type=ledger.类型,  # 追加
)

# 在 valves/__init__.py detail 视图函数中
return render_template("valves/detail.html", valve=valve, from_param=from_param, valve_type=device_type)
```

然后在模板中用 `{% if valve_type == 'electric_valve' %}` 判断。

---

### Task 10: 修改列表模板 list.html

**Files:**
- Modify: `templates/valves/list.html`

- [ ] **Step 1: 替换所有硬编码类型检查**

将 3 处 `ledger.类型 not in ('control_valve', 'onoff_valve')` 替换为 `ledger.类型 not in VALVE_TYPES`：

- 第 44 行（新增按钮）
- 第 159 行（位号链接）
- 第 205 行（详情按钮）、208 行（编辑按钮）

修改示例：
```html
{# 修改前 #}
{% if ledger.类型 not in ('control_valve', 'onoff_valve') %}
{# 修改后 #}
{% if ledger.类型 not in VALVE_TYPES %}
```

- [ ] **Step 2: 追加电动阀电气参数列**

在表头定义（约第 120-135 行）的 `fields` 列表中，在适当位置追加：

```python
                            ('转矩Nm', '转矩Nm', ''), ('功率', '功率', ''),
                            ('转速r/min', '转速', ''), ('转圈数r', '转圈数', ''),
                            ('电源', '电源', ''), ('防护等级', '防护等级', ''),
```

并增加 `colspan` 值（第 111-116 行的表头分组需要调整）。

同时增加数据行显示（在约第 168 行之后追加）：
```html
                        <td class="cmp-table__td">{{ valve.转矩Nm or '-' }}</td>
                        <td class="cmp-table__td">{{ valve.功率 or '-' }}</td>
                        <td class="cmp-table__td">{{ valve.转速r/min or '-' }}</td>
                        <td class="cmp-table__td">{{ valve.转圈数r or '-' }}</td>
                        <td class="cmp-table__td">{{ valve.电源 or '-' }}</td>
                        <td class="cmp-table__td">{{ valve.防护等级 or '-' }}</td>
```

---

### Task 11: 修改维护记录模板

**Files:**
- Modify: `templates/maintenance/list.html`

- [ ] **Step 1: 替换硬编码类型检查**

第 91 行：
```html
{% elif record.device_type in ('control_valve', 'onoff_valve') %}
```
改为：
```html
{% elif record.device_type in VALVE_TYPES %}
```

---

### Task 12: 创建数据库表

- [ ] **Step 1: 创建 electric_valves 表**

如果使用现有数据库（valves.db），需要创建新表。Flask shell 中执行：

```python
from app import create_app, db
from app.devices.types.electric_valve import ElectricValve
app = create_app()
with app.app_context():
    ElectricValve.__table__.create(db.engine)
    print("electric_valves table created")
```

如果数据库已存在 `electric_valves` 表则跳过。

---

## Self-Review

**1. 需求覆盖：**
- [x] 模型：ElectricValve 类 ✓（Task 1）
- [x] 注册到 DeviceTypeRegistry ✓（Task 2）
- [x] VALVE_TYPES 列表加入电动阀 ✓（Task 3）
- [x] 导入引擎 aware ✓（Task 4-6）
- [x] 前端表单 ✓（Task 8）
- [x] 前端详情 ✓（Task 9）
- [x] 前端列表 ✓（Task 10）
- [x] 维护记录链接 ✓（Task 11）
- [x] 数据库表创建 ✓（Task 12）

**2. 占位符检查：** 所有步骤包含完整代码，无 TBD/TODO。

**3. 类型一致性：** ElectricValve 属性名与模板/column_mapping 中使用的名称一致（`转矩Nm`、`功率`、`转速r/min`、`转圈数r`、`电源`、`防护等级`）。

**4. 路由兼容性：**
- `ledgers.py` 已使用 `VALVE_TYPES` 动态判断（line 380, 819）— 自动适配
- `imports.py` 已使用 `VALVE_TYPES`（line 631）— 自动适配
- 仅模板中的 4 处硬编码需要修改（Task 10-11）
- `valves/__init__.py` 中的 `detail` 视图（line 92）已使用 `device_type in VALVE_TYPES` — 自动适配
