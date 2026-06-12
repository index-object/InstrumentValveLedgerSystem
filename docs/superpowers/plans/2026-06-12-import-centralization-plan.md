# 导入模块集中化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将所有设备类型的导入功能集中到统一的 `/imports` 界面，消除散落的独立导入路由。

**Architecture:** 增强现有 `ImportEngine`（`DataLoader` 增加 `preserve_order` 参数）；`imports` 蓝图的 `execute()` 路由增加阀门附件处理 + 自动创建 Ledger 逻辑；将散落导入路由改为重定向；添加侧边栏和首页导航入口。

**Tech Stack:** Flask, SQLAlchemy, openpyxl, ImportEngine

---

### Task 1: 为 DataLoader 增加 preserve_order 参数

**Files:**
- Modify: `app/import_engine/loader.py`

- [ ] **Step 1: 修改 `create_records` 方法，添加 `preserve_order` 参数**

```python
def create_records(
    self,
    model_class: type,
    rows: list[dict[str, str]],
    preserve_order: bool = False,
) -> list[Any]:
    records = [self.create_record(model_class, row) for row in rows]
    if not preserve_order:
        records.sort(key=lambda r: self._sort_key(r))
    return records
```

- [ ] **Step 2: 更新 `engine.py` 中调用 `create_records` 的地方，传递 `preserve_order` 参数**

打开 `app/import_engine/engine.py`，在文件顶部添加导入：
```python
from app.models import Valve
```

找到：
```python
records = self._loader.create_records(model_cls, mapped_rows)
```
修改为：
```python
preserve = model_cls is Valve
records = self._loader.create_records(model_cls, mapped_rows, preserve_order=preserve)
```

- [ ] **Step 3: 验证修改不破坏现有逻辑**

Run: `python -m pytest tests/import_engine/ -v`
Expected: 所有测试通过

- [ ] **Step 4: 提交**

```bash
git add app/import_engine/loader.py app/import_engine/engine.py
git commit -m "feat: DataLoader 增加 preserve_order 参数，阀门类型不排序"
```

---

### Task 2: 在 app/__init__.py 中注册 imports 蓝图

**Files:**
- Modify: `app/__init__.py`

- [ ] **Step 1: 添加 imports 蓝图导入和注册**

在 `app/__init__.py` 的导入部分添加：
```python
from app.routes.imports import imports
```

在 `app.register_blueprint(ledgers)` 之后添加：
```python
app.register_blueprint(imports)
```

- [ ] **Step 2: 验证蓝图正确注册**

Run: `python -c "from app import create_app; app = create_app(); print([r.rule for r in app.url_map.iter_rules() if 'import' in r.rule])"`
Expected: 输出包含 `/imports`、`/imports/upload`、`/imports/preview` 等路由

- [ ] **Step 3: 提交**

```bash
git add app/__init__.py
git commit -m "fix: 注册 imports 蓝图到 Flask 应用"
```

---

### Task 3: 增强 imports 的 execute 路由 — 阀门附件 + 自动创建 Ledger

**Files:**
- Modify: `app/routes/imports.py`

- [ ] **Step 1: 在文件头部添加新导入**

```python
from app.models import db, Ledger, Valve, ValveAttachment
from app.devices import DeviceTypeRegistry
from datetime import datetime
```

- [ ] **Step 2: 在 execute 函数中添加附件类型推断辅助函数**

在 `get_engine()` 函数之后添加：
```python
def _infer_attachment_type(name: str) -> str:
    keywords = {
        "定位器": ["定位器"],
        "电磁阀": ["电磁阀"],
        "过滤器": ["过滤器"],
        "减压阀": ["减压阀"],
        "保位阀": ["保位阀"],
        "放大器": ["放大器"],
        "转换器": ["转换器"],
        "限位开关": ["限位开关"],
        "位置变送器": ["位置变送器"],
    }
    for att_type, kw_list in keywords.items():
        for kw in kw_list:
            if kw in name:
                return att_type
    return name
```

- [ ] **Step 3: 替换 `execute()` 函数，增加附件处理和自动创建 Ledger**

完整替换 `execute` 函数：

```python
@imports.route("/imports/execute", methods=["POST"])
@login_required
def execute():
    saved_name = session.get("import_file")
    if not saved_name:
        flash("找不到已上传的文件，请重新上传")
        return redirect(url_for("imports.index"))

    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    saved_path = os.path.join(upload_folder, saved_name)
    if not os.path.exists(saved_path):
        flash("临时文件丢失，请重新上传")
        return redirect(url_for("imports.index"))

    engine = get_engine()
    try:
        result = engine.import_file(saved_path)
    except Exception as e:
        flash(f"文件读取失败: {e}")
        return redirect(url_for("imports.index"))

    mappings = session.get("import_mappings") or {}
    merge_config = {}
    ledger_name_overrides = {}
    for key, value in request.form.items():
        if key.startswith("merge_"):
            sheet_name = key[len("merge_"):]
            if value == "1":
                merge_config[sheet_name] = True
        elif key.startswith("ledger_name_"):
            sheet_name = key[len("ledger_name_"):]
            if value:
                ledger_name_overrides[sheet_name] = value.strip()

    total_created = 0
    per_sheet = []
    type_ledgers = {}

    for sr in result.sheets:
        sheet_name = sr.sheet_name

        type_code = sr.type_code
        if sr.type_key and sr.type_key in mappings:
            type_code = mappings[sr.type_key]

        if not type_code or type_code in ("summary", "cover"):
            per_sheet.append({"sheet": sheet_name, "created": 0, "skipped": True})
            continue

        # 查找或创建 Ledger
        device_config = DeviceTypeRegistry.get(type_code)
        if merge_config.get(sheet_name) and type_code in type_ledgers:
            ledger = type_ledgers[type_code]
        else:
            ledger_name = ledger_name_overrides.get(sheet_name, sheet_name)

            ledger = Ledger.query.filter_by(
                名称=ledger_name, 类型=type_code, created_by=current_user.id
            ).first()
            if not ledger:
                ledger = Ledger()
                ledger.名称 = ledger_name
                ledger.描述 = f"由用户 {current_user.username} 导入于 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                ledger.类型 = type_code
                ledger.created_by = current_user.id
                ledger.status = "draft"
                db.session.add(ledger)
                db.session.flush()

            if merge_config.get(sheet_name):
                type_ledgers[type_code] = ledger

        # 写入记录
        created = 0
        for record in sr.records:
            record.ledger_id = ledger.id
            record.created_by = current_user.id
            record.status = "draft"
            db.session.add(record)
            created += 1

        # 阀门附件处理（所有使用 Valve 模型的类型）
        device_config = DeviceTypeRegistry.get(type_code)
        is_valve_type = device_config and device_config.model_class and device_config.model_class.__name__ == "Valve"
        if is_valve_type and sr.accessories:
            acc_idx = 0
            for record in sr.records:
                if not record.id:
                    continue
                while acc_idx < len(sr.accessories):
                    acc = sr.accessories[acc_idx]
                    acc_idx += 1
                    name = acc.get("名称", "")
                    attachment = ValveAttachment(
                        valve_id=record.id,
                        名称=name,
                        type=_infer_attachment_type(name),
                        型号规格=acc.get("型号规格", ""),
                        生产厂家=acc.get("生产厂家", ""),
                        设备等级=acc.get("设备等级", ""),
                    )
                    db.session.add(attachment)

        per_sheet.append({"sheet": sheet_name, "created": created, "skipped": False})
        total_created += created

    db.session.commit()

    try:
        os.remove(saved_path)
    except Exception:
        pass
    for key in (
        "import_file", "import_preview", "import_errors",
        "import_mappings", "import_filename",
    ):
        session.pop(key, None)

    flash(f"导入完成：共创建 {total_created} 条记录")
    return redirect(url_for("imports.index"))
```

- [ ] **Step 4: 提交**

```bash
git add app/routes/imports.py
git commit -m "feat: imports execute 增加阀门附件处理和自动创建 Ledger"
```

---

### Task 4: 将 devices.py 的 import_data 改为重定向

**Files:**
- Modify: `app/routes/devices.py`

- [ ] **Step 1: 替换 `import_data` 函数为重定向**

将 `devices.py` 中 `import_data` 函数（第 335-381 行）的内容替换为：

```python
@devices_bp.route("/<type_code>/import", methods=["GET", "POST"])
@login_required
def import_data(type_code):
    config = get_config_or_404(type_code)
    flash(f"导入功能已统一迁移到「导入数据」页面")
    return redirect(url_for("imports.index"))
```

- [ ] **Step 2: 提交**

```bash
git add app/routes/devices.py
git commit -m "refactor: devices import_data 改为重定向到统一导入页面"
```

---

### Task 5: 删除 valves/import 和 valves/import/execute 路由

**Files:**
- Modify: `app/routes/valves/exports.py`

- [ ] **Step 1: 删除 `import_data` 和 `import_execute` 函数**

从 `app/routes/valves/exports.py` 中：
- 删除 `import_data()` 函数（第 22-121 行）
- 删除 `import_execute()` 函数（第 124-236 行）

- [ ] **Step 2: 移除路由注册**

找到 `register_export_routes` 函数，将：
```python
bp.route("/import", methods=["GET", "POST"])(
    login_required(require_employee_or_admin(import_data))
)
bp.route("/import/execute", methods=["POST"])(
    login_required(require_employee_or_admin(import_execute))
)
```
替换为：
```python
# 导入功能已迁移到 /imports 统一界面
```

- [ ] **Step 3: 清理不再需要的导入**

移除以下不再使用的导入：
- `session` — 仅 import 路由使用
- `jsonify` — 仅 import 路由使用
- `Setting` — 仅 `import_execute` 使用
- `ValveAttachment` — 仅 `import_execute` 使用
- `require_employee_or_admin` — 仅装饰 import 路由
- `process_import_preview` — 仅 `import_data` 使用

保留以下仍在使用的导入：
- `flash`, `redirect`, `url_for`, `request`, `render_template`, `make_response` — 被 `export_data` 和 `export_valve_pdf` 使用
- `login_required`, `current_user` — 被装饰器和其他函数使用
- `db`, `Valve` — 被 `export_data` 和 `update_ledger_status` 使用
- `get_valve_export_data` — 被 `export_data` 使用
- `datetime` — 被 `export_valve_pdf` 和 `update_ledger_status` 使用
- `BytesIO` — 被 `export_data` 和 `export_valve_pdf` 使用

- [ ] **Step 4: 提交**

```bash
git add app/routes/valves/exports.py
git commit -m "refactor: 移除 valves 独立导入路由，已迁移到统一导入"
```

---

### Task 6: 侧边栏添加导入数据导航

**Files:**
- Modify: `templates/base.html`

- [ ] **Step 1: 在侧边栏菜单中添加导入数据入口**

在 `templates/base.html` 的侧边栏菜单中，在"我的台账"和"全部台账"之间添加（仅在员工角色显示）：

```html
{% if current_user.role == 'employee' %}
<a href="{{ url_for('imports.index') }}" class="sidebar-menu-item {% if request.endpoint and 'imports' in request.endpoint %}active{% endif %}">
    <i class="bi bi-upload"></i><span>导入数据</span>
</a>
{% endif %}
```

- [ ] **Step 2: 提交**

```bash
git add templates/base.html
git commit -m "feat: 侧边栏添加导入数据导航（员工角色）"
```

---

### Task 7: 首页添加导入数据卡片

**Files:**
- Modify: `templates/index_employee.html`

- [ ] **Step 1: 在 stats-grid 中添加导入数据卡片**

在 `index_employee.html` 的 `stats-grid` 中，在"维护记录"卡片之后添加：

```html
<a href="{{ url_for('imports.index') }}" class="stat-card primary">
    <div class="stat-icon primary">
        <i class="bi bi-upload"></i>
    </div>
    <div class="stat-content">
        <h3>导入数据</h3>
        <p>批量导入仪表阀门台账数据</p>
    </div>
</a>
```

- [ ] **Step 2: 提交**

```bash
git add templates/index_employee.html
git commit -m "feat: 首页添加导入数据入口"
```

---

### Task 8: 增强 import.html 模板

**Files:**
- Modify: `templates/imports/import.html`

- [ ] **Step 1: 增强引导说明**

更新 `import.html` 的上传区域说明，突出支持所有设备类型：

```html
<div class="modern-card mb-4">
    <div class="card-header-custom"><i class="bi bi-upload"></i> 批量导入仪表台账</div>
    <div class="card-body-custom">
        <div class="mb-3 p-3" style="background: #f0fdf4; border-radius: 8px; border-left: 3px solid #22c55e;">
            <small class="text-muted">
                <i class="bi bi-info-circle"></i>
                支持所有设备类型：压力表、温度计、流量计、液位计、调节阀、开关阀、开关、特殊仪表等。
                系统将自动识别每个 Sheet 对应的设备类型。支持 .xlsx 和 .xls 格式。
            </small>
        </div>
        <form id="importForm" method="POST" enctype="multipart/form-data" action="{{ url_for('imports.upload') }}">
            <div class="mb-3">
                <label class="form-label">选择 Excel 文件（每个 Sheet 表示一种设备类型）</label>
                <input type="file" name="file" accept=".xlsx,.xls" class="form-control form-control-modern" required>
            </div>
            <div class="mb-3">
                <button type="submit" class="btn btn-primary">上传并预览</button>
                <a href="{{ url_for('ledgers.list') }}" class="btn btn-secondary">返回台账</a>
            </div>
        </form>
    </div>
</div>
```

- [ ] **Step 2: 提交**

```bash
git add templates/imports/import.html
git commit -m "feat: 增强导入页面引导说明"
```

---

### Task 9: 增强 import_preview.html 模板

**Files:**
- Modify: `templates/imports/import_preview.html`

- [ ] **Step 1: 在预览卡片中增加附件数量显示**

在预览卡片的 header 区域，类型名称后添加附件数量：

```html
<span>
    {{ p.sheet }} — {{ p.detected_name or '未识别类型' }} ({{ p.rows }} 行)
    {% if p.accessory_count > 0 %}
    <span class="badge bg-info ms-2">{{ p.accessory_count }} 个附件</span>
    {% endif %}
</span>
```

同时，在卡片 header 中显示设备类型图标（如果有的话）。

- [ ] **Step 2: 提交**

```bash
git add templates/imports/import_preview.html
git commit -m "feat: 预览页面增加附件数量显示"
```

---

### Task 10: 清理不再使用的模板文件

**Files:**
- Delete: `templates/devices/import.html`
- Delete: `templates/valves/import.html`
- Delete: `templates/valves/import_preview.html`

- [ ] **Step 1: 确认模板不再被任何路由引用**

检查是否有其他路由引用了这些模板：
```bash
rg "devices/import\.html" app/ templates/
rg "valves/import\.html" app/ templates/
rg "valves/import_preview\.html" app/ templates/
```
预期：所有搜索结果只来自即将删除的文件本身。

- [ ] **Step 2: 删除模板文件**

```bash
git rm templates/devices/import.html templates/valves/import.html templates/valves/import_preview.html
```

- [ ] **Step 3: 验证应用启动正常**

Run: `python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: 输出 OK，无 ImportError

- [ ] **Step 4: 提交**

```bash
git commit -m "cleanup: 删除不再使用的独立导入模板"
```

---

### Task 11: 运行测试验证

- [ ] **Step 1: 运行现有测试**

Run: `python -m pytest tests/ -v`
Expected: 所有测试通过（如有失败需排查是否由上述改动引起）

- [ ] **Step 2: 整体验证**

Run: `python -c "from app import create_app; app = create_app(); print('应用启动正常')"`
Expected: 输出"应用启动正常"

- [ ] **Step 3: 如果测试通过，做最终提交**

```bash
git add -A && git commit -m "chore: 导入集中化完成，测试通过"
```
