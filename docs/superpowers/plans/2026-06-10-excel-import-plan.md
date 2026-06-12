# Excel 批量导入功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现从 Excel 文件批量导入台账数据，自动识别或手动指定设备类型，自动创建台账合集。

**架构：** 上传 → 安全解析 → 类型检测 → 未识别弹窗 → 预览（含合并选项）→ 执行导入。在现有 form 提交流程基础上，增加 JS 弹窗处理未识别类型。

**Tech Stack:** Flask, openpyxl, SQLAlchemy, Bootstrap 5 (已有), vanilla JS

---

### Task 1: 创建 Safe Excel 读取工具函数

**Files:**
- Create: `app/utils/importer.py`

创建一个安全的 Excel 读取函数，绕过 externalLinks 导致 openpyxl 卡死的问题。

- [ ] **Step 1: 创建文件并实现 safe_read_excel**

`app/utils/importer.py`:
```python
import zipfile
import tempfile
import os
import shutil
from openpyxl import load_workbook


def safe_read_excel(filepath):
    """安全读取 Excel，移除 externalLinks 避免 openpyxl 挂起"""
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    try:
        with zipfile.ZipFile(filepath) as zin:
            with zipfile.ZipFile(tmp.name, "w") as zout:
                for item in zin.infolist():
                    if not item.filename.startswith("xl/externalLinks"):
                        zout.writestr(item, zin.read(item.filename))
        wb = load_workbook(tmp.name, read_only=True, data_only=True)
        result = []
        for s in wb.sheetnames:
            ws = wb[s]
            headers = []
            rows_data = []
            row_count = 0
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i == 0:
                    headers = [str(c).strip() if c else "" for c in row]
                else:
                    row_dict = {}
                    for j, cell in enumerate(row):
                        col_name = headers[j] if j < len(headers) else f"col{j}"
                        row_dict[col_name] = str(cell).strip() if cell is not None else ""
                    if any(v for v in row_dict.values()):
                        rows_data.append(row_dict)
                        row_count += 1
            result.append({
                "sheet": s,
                "columns": headers,
                "rows": rows_data,
                "row_count": row_count,
                "sample": rows_data[:5],
            })
        wb.close()
        return result
    finally:
        try:
            os.unlink(tmp.name)
        except:
            pass
```

- [ ] **Step 2: 运行验证**

```bash
cd /d E:\项目服务\value\InstrumentValveLedgerSystem && .venv\Scripts\python.exe -c "from app.utils.importer import safe_read_excel; data=safe_read_excel('导入台账示例.xlsx'); print([d['sheet'] for d in data])"
```

Expected: 打印所有 Sheet 名，无卡死

- [ ] **Step 3: Commit**

```bash
git add app/utils/importer.py
git commit -m "feat: add safe_read_excel utility"
```

---

### Task 2: 修改 upload 路由，使用 safe_read_excel + 支持未识别 Sheet

**Files:**
- Modify: `app/routes/imports.py` (lines 37-94)
- Keep: 现有路由结构

- [ ] **Step 1: 修改 upload 函数**

改动点：
1. 导入 `from app.utils.importer import safe_read_excel`
2. 用 `safe_read_excel` 替换 `pd.read_excel`
3. 类型检测后，将未识别的 Sheet 信息和数据都存入 session
4. 有未识别时返回 `import.html` 页面（带 unmatched 数据让 JS 弹窗）
5. 全部识别时直接跳转到新 `/imports/preview` 页面

修改 `app/routes/imports.py` 的 `upload()` 函数：

```python
@imports.route("/imports/upload", methods=["POST"])
@login_required
def upload():
    if "file" not in request.files:
        flash("请选择文件")
        return redirect(url_for("imports.index"))

    file = request.files["file"]
    if file.filename == "":
        flash("请选择文件")
        return redirect(url_for("imports.index"))

    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".xlsx", ".xls"):
        flash("仅支持 .xlsx / .xls 文件")
        return redirect(url_for("imports.index"))

    uid = uuid.uuid4().hex
    saved_name = f"import_{uid}{ext}"
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    saved_path = os.path.join(upload_folder, saved_name)
    file.save(saved_path)

    try:
        sheets_data = safe_read_excel(saved_path)
    except Exception as e:
        flash(f"文件读取失败: {e}")
        try:
            os.remove(saved_path)
        except:
            pass
        return redirect(url_for("imports.index"))

    preview = []
    unmatched = []
    for sd in sheets_data:
        cfg = detect_device_type(sd["sheet"])
        preview.append({
            "sheet": sd["sheet"],
            "rows": sd["row_count"],
            "columns": sd["columns"],
            "sample": sd["sample"],
            "detected_type": cfg.code if cfg else None,
            "detected_name": cfg.name if cfg else None,
        })
        if not cfg:
            unmatched.append(sd["sheet"])

    session["multi_import_file"] = saved_name
    session["multi_import_preview"] = preview
    session["multi_import_raw"] = [{k: v for k, v in sd.items()} for sd in sheets_data]
    session.pop("import_mappings", None)

    if unmatched:
        return render_template("imports/import.html",
            unmatched=unmatched,
            all_types=[{"code": t.code, "name": t.name} for t in DeviceTypeRegistry.all()],
            filename=filename)

    return redirect(url_for("imports.preview"))
```

- [ ] **Step 2: 创建 preview 路由**

新增：
```python
@imports.route("/imports/preview")
@login_required
def preview():
    preview_data = session.get("multi_import_preview")
    filename = request.args.get("filename", "导入文件")
    if not preview_data:
        flash("没有预览数据，请重新上传")
        return redirect(url_for("imports.index"))
    return render_template("imports/import_preview.html", preview=preview_data, filename=filename)
```

同时修改 `imports/import.html` 的 action 为 `url_for('imports.upload')`，不做改动。

- [ ] **Step 3: Commit**

```bash
git add app/routes/imports.py app/utils/importer.py
git commit -m "feat: update upload route with safe excel read and unmatched handling"
```

---

### Task 3: 创建 type-select 弹窗 HTML 和 JS

**Files:**
- Modify: `templates/imports/import.html`
- Create: `static/js/import.js`

- [ ] **Step 1: 修改 import.html**

添加弹窗模板，当有 `unmatched` 数据时显示：

```html
{% extends "base.html" %}

{% block page_title %}导入管理{% endblock %}

{% block content %}
<div class="modern-card mb-4">
    <div class="card-header-custom"><i class="bi bi-upload"></i> 批量导入台账</div>
    <div class="card-body-custom">
        <form id="importForm" method="POST" enctype="multipart/form-data" action="{{ url_for('imports.upload') }}">
            <div class="mb-3">
                <label class="form-label">选择 Excel 文件（每个 sheet 表示一种设备类型）</label>
                <input type="file" name="file" accept=".xlsx,.xls" class="form-control form-control-modern" required>
            </div>
            <div class="mb-3">
                <button type="submit" class="btn btn-primary">上传并预览</button>
                <a href="{{ url_for('ledgers.list') }}" class="btn btn-secondary">返回台账</a>
            </div>
        </form>
    </div>
</div>

{% if unmatched %}
<div class="modal fade show" id="typeModal" tabindex="-1" style="display:block;background:rgba(0,0,0,0.5);">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">选择设备类型</h5>
            </div>
            <form method="POST" action="{{ url_for('imports.save_mapping') }}">
                <div class="modal-body">
                    <p>以下 Sheet 无法自动识别设备类型，请为每个 Sheet 指定对应类型：</p>
                    {% for s in unmatched %}
                    <div class="mb-3">
                        <label class="form-label">{{ s }}</label>
                        <select name="mapping_{{ s }}" class="form-select">
                            <option value="">-- 跳过此 Sheet --</option>
                            {% for t in all_types %}
                            <option value="{{ t.code }}">{{ t.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    {% endfor %}
                </div>
                <div class="modal-footer">
                    <a href="{{ url_for('imports.index') }}" class="btn btn-secondary">取消</a>
                    <button type="submit" class="btn btn-primary">确认</button>
                </div>
            </form>
        </div>
    </div>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: 创建 import.js**

`static/js/import.js`:
```javascript
document.addEventListener('DOMContentLoaded', function() {
    var modal = document.getElementById('typeModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                // don't close on backdrop click - force user to make a choice
            }
        });
    }
});
```

在 `base.html` 中检查是否引入了 `import.js`，或直接在 `import.html` 模板中内联。

- [ ] **Step 3: 创建 save_mapping 路由**

```python
@imports.route("/imports/save-mapping", methods=["POST"])
@login_required
def save_mapping():
    raw_data = session.get("multi_import_raw")
    if not raw_data:
        flash("会话过期，请重新上传")
        return redirect(url_for("imports.index"))

    mappings = {}
    for key, value in request.form.items():
        if key.startswith("mapping_"):
            sheet_name = key[len("mapping_"):]
            if value:
                mappings[sheet_name] = value

    session["import_mappings"] = mappings
    return redirect(url_for("imports.preview"))
```

- [ ] **Step 4: Commit**

```bash
git add templates/imports/import.html static/js/import.js app/routes/imports.py
git commit -m "feat: add type selection modal for unmatched sheets"
```

---

### Task 4: 修改 preview 页面——添加合并选项

**Files:**
- Modify: `templates/imports/import_preview.html`

- [ ] **Step 1: 修改预览模板**

在预览页为每个 Sheet 添加合并选项和台账名称输入框：

```html
{% extends "base.html" %}

{% block page_title %}导入预览{% endblock %}

{% block content %}
<div class="container-fluid">
    <h2>导入预览 - {{ filename }}</h2>

    <form method="POST" action="{{ url_for('imports.execute') }}">
        <div class="mb-3">
            {{ form.csrf_token }}
            <button type="submit" class="btn btn-success">确认导入</button>
            <a href="{{ url_for('imports.index') }}" class="btn btn-secondary">重新上传</a>
        </div>

        {% for p in preview %}
        <div class="card mb-3">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span>
                    {{ p.sheet }} —— {{ p.detected_name or '未识别类型' }} ({{ p.rows }} 行)
                </span>
                <div class="form-check">
                    <input class="form-check-input merge-checkbox" type="checkbox"
                           name="merge_{{ p.sheet }}" value="1"
                           id="merge_{{ loop.index }}"
                           data-type="{{ p.detected_type }}">
                    <label class="form-check-label" for="merge_{{ loop.index }}">
                        合并到同类型台账合集
                    </label>
                </div>
            </div>
            <div class="card-body">
                <div class="mb-2">
                    <label class="form-label">台账合集名称</label>
                    <input type="text" class="form-control form-control-sm ledger-name-input"
                           name="ledger_name_{{ p.sheet }}" value="{{ p.sheet }}"
                           style="max-width:300px;">
                </div>
                {% if p.sample %}
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                {% for h in p.sample[0].keys() %}
                                <th>{{ h }}</th>
                                {% endfor %}
                            </tr>
                        </thead>
                        <tbody>
                            {% for r in p.sample %}
                            <tr>
                                {% for v in r.values() %}
                                <td>{{ v }}</td>
                                {% endfor %}
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% else %}
                <div class="text-muted">无预览数据</div>
                {% endif %}
            </div>
        </div>
        {% endfor %}

        <div class="mb-3">
            <button type="submit" class="btn btn-success">确认导入</button>
            <a href="{{ url_for('imports.index') }}" class="btn btn-secondary">重新上传</a>
        </div>
    </form>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    var merges = {};
    document.querySelectorAll('.merge-checkbox').forEach(function(cb) {
        cb.addEventListener('change', function() {
            var type = this.dataset.type;
            if (this.checked) {
                merges[type] = merges[type] || [];
                merges[type].push(this.closest('.card'));
            }
            // 同类型第一个 sheet 的名称作为合并后的台账名
            // 这里仅做视觉提示，逻辑在服务端处理
        });
    });
});
</script>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add templates/imports/import_preview.html
git commit -m "feat: add merge options to import preview"
```

---

### Task 5: 修改 execute 路由——使用映射 + 合并逻辑

**Files:**
- Modify: `app/routes/imports.py` (execute 函数)

- [ ] **Step 1: 重写 execute 函数**

```python
@imports.route("/imports/execute", methods=["POST"])
@login_required
def execute():
    saved_name = session.get("multi_import_file")
    if not saved_name:
        flash("找不到已上传的文件，请重新上传")
        return redirect(url_for("imports.index"))

    raw_data = session.get("multi_import_raw")
    mappings = session.get("import_mappings") or {}

    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    saved_path = os.path.join(upload_folder, saved_name)
    if not os.path.exists(saved_path):
        flash("临时文件丢失，请重新上传")
        return redirect(url_for("imports.index"))

    try:
        sheets_data = safe_read_excel(saved_path)
    except Exception as e:
        flash(f"文件读取失败: {e}")
        return redirect(url_for("imports.index"))

    # 构建合并配置
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
                ledger_name_overrides[sheet_name] = value

    total_created = 0
    per_sheet = []
    type_ledgers = {}

    for sd in sheets_data:
        sheet_name = sd["sheet"]
        # 确定类型：先看用户映射，再看自动检测
        cfg = None
        if sheet_name in mappings:
            if mappings[sheet_name]:
                cfg = DeviceTypeRegistry.get(mappings[sheet_name])
        if not cfg:
            cfg = detect_device_type(sheet_name)
        if not cfg:
            per_sheet.append({"sheet": sheet_name, "created": 0, "skipped": True})
            continue

        type_code = cfg.code

        # 确定 Ledger
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
                ledger.描述 = f"由用户 {current_user.username} 导入于导入功能创建"
                ledger.类型 = type_code
                ledger.created_by = current_user.id
                ledger.status = "draft"
                db.session.add(ledger)
                db.session.flush()
            if merge_config.get(sheet_name):
                type_ledgers[type_code] = ledger

        created = 0
        model_cls = cfg.model_class
        for row in sd["rows"]:
            if not model_cls:
                continue
            inst = model_cls()
            inst.ledger_id = ledger.id
            inst.created_by = current_user.id
            inst.status = "draft"
            for col, val in row.items():
                if hasattr(inst, col) and val:
                    try:
                        setattr(inst, col, val)
                    except Exception:
                        pass
            db.session.add(inst)
            created += 1

        per_sheet.append({"sheet": sheet_name, "created": created, "skipped": False})
        total_created += created

    db.session.commit()

    try:
        os.remove(saved_path)
    except:
        pass
    session.pop("multi_import_file", None)
    session.pop("multi_import_preview", None)
    session.pop("multi_import_raw", None)
    session.pop("import_mappings", None)

    flash(f"导入完成：共创建 {total_created} 条记录")
    return redirect(url_for("ledgers.list"))
```

- [ ] **Step 2: 确保 safe_read_excel 在 execute 前已有数据**

实际上 execute 重新读取了文件，所以没问题。但要注意 `safe_read_excel` 在有 externalLinks 的文件上已正常工作。

- [ ] **Step 3: Commit**

```bash
git add app/routes/imports.py
git commit -m "feat: update execute route with type mappings and merge support"
```

---

### Task 6: 注册新路由 + 完整流程测试

**Files:**
- Modify: `app/routes/imports.py` — 确保所有新路由已注册（在同一个 Blueprint 中自动注册）

- [ ] **Step 1: 验证所有路由**

确保 Blueprint 中有：
- `imports.route("/imports")` — GET, index
- `imports.route("/imports/upload")` — POST, upload
- `imports.route("/imports/save-mapping")` — POST, save_mapping
- `imports.route("/imports/preview")` — GET, preview
- `imports.route("/imports/execute")` — POST, execute

- [ ] **Step 2: 手动测试**

```bash
cd /d E:\项目服务\value\InstrumentValveLedgerSystem && .venv\Scripts\python.exe main.py
```

1. 访问 `/imports` 上传 `导入台账示例.xlsx`
2. 验证弹窗显示未识别 Sheet
3. 选择类型后确认
4. 验证预览页显示所有 Sheet + 合并选项
5. 执行导入
6. 验证台账列表页面有新建的 Ledger

- [ ] **Step 3: 修复发现的问题**

- [ ] **Step 4: Commit**

```bash
git add app/routes/imports.py
git commit -m "feat: complete excel import flow with type selection and merge"
```

---

## 文件变更汇总

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/utils/importer.py` | 新建 | `safe_read_excel()` 安全读取 Excel |
| `app/routes/imports.py` | 修改 | upload/preview/save_mapping/execute 四个路由 |
| `templates/imports/import.html` | 修改 | 添加未识别类型弹窗模板 |
| `templates/imports/import_preview.html` | 修改 | 添加合并选项+台账名称输入 |
| `static/js/import.js` | 新建 | 前端交互（可选的，弹窗可用纯 CSS） |
