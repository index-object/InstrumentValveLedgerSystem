# 数据去重实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 防止同类型表中导入或新增重复的"装置名称+位号"数据，导入时支持跳过/覆盖/中止三种模式，手动新增时实时检测

**Architecture:** 纯应用层校验方案，创建通用 `check_duplicate` 工具函数，在导入预检/执行和手动新增编辑环节分别调用

**Tech Stack:** Python/Flask/SQLAlchemy/SQLite

---

### Task 1: 通用重复检测工具函数

**Files:**
- Create: `app/utils/duplicate_check.py`
- Test: `tests/test_duplicate_check.py`

- [ ] **Step 1: 创建 `app/utils/duplicate_check.py`**

```python
def check_duplicate(model_class, unit_name, tag_no, exclude_id=None):
    """检查同类型表中是否存在相同的装置名称+位号组合（排除草稿状态）"""
    if not unit_name or not tag_no:
        return False
    q = model_class.query.filter(
        model_class.装置名称 == unit_name,
        model_class.位号 == tag_no,
        model_class.status != "draft",
    )
    if exclude_id:
        q = q.filter(model_class.id != exclude_id)
    return q.first() is not None
```

- [ ] **Step 2: 创建 `tests/test_duplicate_check.py`**

```python
import pytest
from app.utils.duplicate_check import check_duplicate


class MockDevice:
    id: int = 0
    装置名称: str = ""
    位号: str = ""
    status: str = "draft"

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockQuery:
    def __init__(self, records):
        self.records = records
        self._filters = {}

    def filter(self, *args):
        return self

    def filter_by(self, **kwargs):
        result = self.records
        for k, v in kwargs.items():
            if k == "status":
                result = [r for r in result if r.status != v]
        return MockQuery(result)

    def __getattr__(self, name):
        class Field:
            def __eq__(self, other):
                return True
            def __ne__(self, other):
                return True
        return Field()

    def first(self):
        return self.records[0] if self.records else None


class TestCheckDuplicate:
    def test_duplicate_found(self):
        class FakeModel:
            query = MockQuery([
                MockDevice(装置名称="装置A", 位号="TAG-001", status="approved")
            ])
        assert check_duplicate(FakeModel, "装置A", "TAG-001") is True

    def test_no_duplicate(self):
        class FakeModel:
            query = MockQuery([])
        assert check_duplicate(FakeModel, "装置A", "TAG-999") is False

    def test_draft_excluded(self):
        class FakeModel:
            query = MockQuery([
                MockDevice(装置名称="装置A", 位号="TAG-001", status="draft")
            ])
        assert check_duplicate(FakeModel, "装置A", "TAG-001") is False

    def test_exclude_id(self):
        dev = MockDevice(id=1, 装置名称="装置A", 位号="TAG-001", status="approved")
        class FakeModel:
            query = MockQuery([dev])
        assert check_duplicate(FakeModel, "装置A", "TAG-001", exclude_id=1) is False

    def test_empty_unit_name_returns_false(self):
        class FakeModel:
            query = MockQuery([])
        assert check_duplicate(FakeModel, "", "TAG-001") is False

    def test_empty_tag_no_returns_false(self):
        class FakeModel:
            query = MockQuery([])
        assert check_duplicate(FakeModel, "装置A", "") is False
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd /d E:\项目服务\value\InstrumentValveLedgerSystem && .venv\Scripts\pytest tests\test_duplicate_check.py -v`
Expected: 6 passed

- [ ] **Step 4: Commit**

```bash
git add app/utils/duplicate_check.py tests/test_duplicate_check.py
git commit -m "feat: 通用重复检测工具函数 check_duplicate"
```

---

### Task 2: 修改 check-tag 接口，支持装置名称+位号联合检测

**Files:**
- Modify: `app/routes/devices.py:318-337`

- [ ] **Step 1: 修改 check-tag 路由**

将 `app/routes/devices.py:` 中的 `check_tag` 函数改为同时检测装置名称+位号：

```python
@devices_bp.route("/<type_code>/check-tag")
@login_required
def check_tag(type_code):
    config = get_config_or_404(type_code)
    model = config.model_class

    位号 = request.args.get("位号")
    装置名称 = request.args.get("装置名称")
    if not 位号:
        return jsonify({"valid": True})

    exclude_id = request.args.get("exclude_id", type=int)
    exists = check_duplicate(model, 装置名称, 位号, exclude_id)
    return jsonify({"valid": not exists, "message": "该装置下此位号已存在" if exists else None})
```

- [ ] **Step 2: 修改 devices/form.html 的 JS，加入装置名称参数**

原代码仅检测位号，修改为同时发送装置名称：

```html
<script>
document.querySelectorAll('[data-check-tag]').forEach(input => {
  function checkDuplicate() {
    const tag = input.value.trim();
    const type = input.dataset.type;
    const unitInput = document.querySelector('input[name="装置名称"]');
    const unitName = unitInput ? unitInput.value.trim() : '';
    if (!tag) return;
    const params = new URLSearchParams({位号: tag});
    if (unitName) params.append('装置名称', unitName);
    fetch(`/device/${type}/check-tag?${params.toString()}`)
      .then(r => r.json())
      .then(data => {
        const existing = input.parentElement.querySelector('.duplicate-warning');
        if (existing) existing.remove();
        if (!data.valid) {
          const warn = document.createElement('div');
          warn.className = 'duplicate-warning text-danger small mt-1';
          warn.textContent = data.message;
          input.parentElement.appendChild(warn);
        }
      });
  }
  input.addEventListener('blur', checkDuplicate);
  input.addEventListener('input', function() {
    const existing = this.parentElement.querySelector('.duplicate-warning');
    if (existing) existing.remove();
  });
});
// 装置名称变化时也触发位号的去重检查
const unitInput = document.querySelector('input[name="装置名称"]');
if (unitInput) {
  unitInput.addEventListener('blur', function() {
    const tagInput = document.querySelector('[data-check-tag]');
    if (tagInput) tagInput.dispatchEvent(new Event('blur'));
  });
}
</script>
```

- [ ] **Step 3: 在 `devices.py` 顶部添加导入**

```python
from app.utils.duplicate_check import check_duplicate
```

- [ ] **Step 4: 运行现有测试确认没破坏东西**

Run: `cd /d E:\项目服务\value\InstrumentValveLedgerSystem && .venv\Scripts\pytest tests/ -v --timeout=30`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add app/routes/devices.py templates/devices/form.html
git commit -m "feat: check-tag 接口支持装置名称+位号联合检测，前端实时提示"
```

---

### Task 3: 修改阀门新增/编辑路由使用新的重复检测

**Files:**
- Modify: `app/routes/ledgers.py:611-682` (new_valve)
- Modify: `app/routes/ledgers.py:685-779` (edit_valve)

- [ ] **Step 1: 在 ledgers.py 顶部添加导入**

```python
from app.utils.duplicate_check import check_duplicate
```

- [ ] **Step 2: 修改 new_valve 路由中的重复检查**

将 `has_duplicate_tag(位号)` 替换为 `check_duplicate(model, 装置名称, 位号)`：

```python
    if request.method == "POST":
        位号 = request.form.get("位号")
        装置名称 = request.form.get("装置名称")
        if 位号 and check_duplicate(model, 装置名称, 位号):
            flash("该装置下此位号已存在，请使用其他位号")
            return redirect(
                url_for("ledgers.new_valve", id=id, **{"from": from_param})
            )
```

- [ ] **Step 3: 在 edit_valve 路由中添加重复检查**

在 POST 处理中，修改位号或装置名称时检查重复（排除自身）：

```python
    if request.method == "POST":
        位号 = request.form.get("位号")
        装置名称 = request.form.get("装置名称")
        if 位号 and check_duplicate(model, 装置名称, 位号, exclude_id=valve.id):
            flash("该装置下此位号已存在")
            return redirect(url_for("ledgers.edit_valve", ledger_id=ledger_id, id=id, **{"from": from_param}))
```

- [ ] **Step 4: 运行现有测试**

Run: `cd /d E:\项目服务\value\InstrumentValveLedgerSystem && .venv\Scripts\pytest tests/ -v --timeout=30`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add app/routes/ledgers.py
git commit -m "feat: 阀门新增/编辑路由改用装置+位号联合重复检测"
```

---

### Task 4: 导入预检阶段增加重复检测

**Files:**
- Modify: `app/routes/imports.py:48-66` (`_build_preview`)
- Modify: `app/routes/imports.py:159-212` (`preview` 路由)
- Modify: `templates/imports/import_preview.html`

- [ ] **Step 1: 修改 `_build_preview` 函数，增加重复检测**

```python
def _build_preview(result):
    """从 ImportResult 构建预览数据和未匹配列表，增加重复检测"""
    from app.utils.duplicate_check import check_duplicate
    from app.devices import DeviceTypeRegistry

    preview = []
    unmatched = []
    for sr in result.sheets:
        if sr.type_code and sr.type_code not in ("summary", "cover"):
            # 查重
            config = DeviceTypeRegistry.get(sr.type_code)
            model_cls = config.model_class if config else None
            duplicates = []
            if model_cls and hasattr(model_cls, "装置名称") and hasattr(model_cls, "位号"):
                for record in sr.records:
                    unit = getattr(record, "装置名称", None) or ""
                    tag = getattr(record, "位号", None) or ""
                    if tag and check_duplicate(model_cls, unit, tag):
                        duplicates.append({"装置名称": unit, "位号": tag})
            preview.append({
                "sheet": sr.sheet_name,
                "rows": sr.row_count,
                "headers": sr.headers,
                "sample": sr.sample_rows,
                "type_key": sr.type_key,
                "detected_type": sr.type_code,
                "detected_name": sr.type_name,
                "accessory_count": sr.accessory_count,
                "duplicates": duplicates,
                "duplicate_count": len(duplicates),
                "new_count": sr.row_count - len(duplicates),
            })
        elif not sr.type_code:
            unmatched.append(sr.sheet_name)
    return preview, unmatched
```

- [ ] **Step 2: 修改导入预览模板，展示重复信息**

在 `templates/imports/import_preview.html` 中，每个 sheet card 的 card-header 后增加：

```html
            {% if p.duplicate_count > 0 %}
            <div class="alert alert-warning mb-2">
                <strong>⚠ 发现 {{ p.duplicate_count }} 条重复记录</strong>
                （本批次 {{ p.rows }} 行中 {{ p.new_count }} 条为新增）
                <button class="btn btn-sm btn-link" type="button" data-bs-toggle="collapse"
                        data-bs-target="#dup-{{ loop.index }}">
                    查看详情
                </button>
                <div class="collapse mt-2" id="dup-{{ loop.index }}">
                    <table class="table table-sm table-bordered mb-0">
                        <thead><tr><th>装置名称</th><th>位号</th></tr></thead>
                        <tbody>
                            {% for d in p.duplicates %}
                            <tr><td>{{ d.装置名称 }}</td><td>{{ d.位号 }}</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                <div class="mt-2">
                    <label class="fw-bold me-2">重复数据处理方式：</label>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="radio"
                               name="dedup_mode_{{ p.sheet }}" value="skip" checked
                               id="skip-{{ loop.index }}">
                        <label class="form-check-label" for="skip-{{ loop.index }}">跳过重复</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="radio"
                               name="dedup_mode_{{ p.sheet }}" value="overwrite"
                               id="overwrite-{{ loop.index }}">
                        <label class="form-check-label" for="overwrite-{{ loop.index }}">覆盖更新</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="radio"
                               name="dedup_mode_{{ p.sheet }}" value="abort"
                               id="abort-{{ loop.index }}">
                        <label class="form-check-label" for="abort-{{ loop.index }}">中止导入</label>
                    </div>
                </div>
            </div>
            {% endif %}
```

- [ ] **Step 3: 运行现有测试**

Run: `cd /d E:\项目服务\value\InstrumentValveLedgerSystem && .venv\Scripts\pytest tests/ -v --timeout=30`
Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add app/routes/imports.py templates/imports/import_preview.html
git commit -m "feat: 导入预检增加重复检测，预览页展示重复详情和操作选项"
```

---

### Task 5: 导入执行阶段支持三种去重模式

**Files:**
- Modify: `app/routes/imports.py:249-387` (execute 路由)

- [ ] **Step 1: 修改 execute 路由，读取去重模式并执行**

将 execute 路由中的写入逻辑替换为根据 dedup_mode 处理：

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
    mappings = session.get("import_mappings") or {}
    try:
        result = engine.import_file(saved_path, type_overrides=mappings)
    except Exception as e:
        flash(f"文件读取失败: {e}")
        return redirect(url_for("imports.index"))

    merge_config = {}
    ledger_name_overrides = {}
    dedup_modes = {}
    for key, value in request.form.items():
        if key.startswith("merge_"):
            sheet_name = key[len("merge_"):]
            if value == "1":
                merge_config[sheet_name] = True
        elif key.startswith("ledger_name_"):
            sheet_name = key[len("ledger_name_"):]
            if value:
                ledger_name_overrides[sheet_name] = value.strip()
        elif key.startswith("dedup_mode_"):
            sheet_name = key[len("dedup_mode_"):]
            dedup_modes[sheet_name] = value

    total_created = 0
    total_skipped = 0
    total_updated = 0
    per_sheet = []
    type_ledgers = {}

    for sr in result.sheets:
        sheet_name = sr.sheet_name

        type_code = sr.type_code
        if sheet_name in mappings:
            type_code = mappings[sheet_name]
        elif sr.type_key and sr.type_key in mappings:
            type_code = mappings[sr.type_key]

        if not type_code or type_code in ("summary", "cover"):
            per_sheet.append({"sheet": sheet_name, "created": 0, "skipped": True})
            continue

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

        dedup_mode = dedup_modes.get(sheet_name, "skip")
        created = 0
        skipped = 0
        updated = 0

        from app.utils.duplicate_check import check_duplicate
        config = DeviceTypeRegistry.get(type_code)
        model_cls = config.model_class if config else None

        # 中止模式：预检所有记录
        if dedup_mode == "abort" and model_cls:
            abort_duplicates = []
            for record in sr.records:
                unit = getattr(record, "装置名称", None) or ""
                tag = getattr(record, "位号", None) or ""
                if tag and check_duplicate(model_cls, unit, tag):
                    abort_duplicates.append(f"{unit}/{tag}")
            if abort_duplicates:
                flash(f"[{sheet_name}] 发现 {len(abort_duplicates)} 条重复记录，导入已中止")
                continue

        seen_tags = {}
        for record in sr.records:
            record.ledger_id = ledger.id
            record.created_by = current_user.id
            record.status = "draft"

            tag = getattr(record, "位号", None)
            if tag:
                tag = tag.strip()
            if not tag or tag in ("/", "-"):
                continue

            unit = getattr(record, "装置名称", None) or ""

            # 同批次内去重
            batch_key = f"{unit}|{tag}"
            if batch_key in seen_tags:
                skipped += 1
                continue
            seen_tags[batch_key] = True

            if model_cls and check_duplicate(model_cls, unit, tag):
                if dedup_mode == "skip":
                    skipped += 1
                    continue
                elif dedup_mode == "overwrite":
                    existing = model_cls.query.filter(
                        model_cls.装置名称 == unit,
                        model_cls.位号 == tag,
                        model_cls.status != "draft",
                    ).first()
                    if existing:
                        for col in model_cls.__table__.columns:
                            col_name = col.name
                            if col_name not in ("id", "ledger_id", "created_by", "created_at", "status", "updated_at", "approved_by", "approved_at"):
                                setattr(existing, col_name, getattr(record, col_name, None))
                        existing.updated_at = datetime.utcnow()
                        updated += 1
                        continue

            db.session.add(record)
            created += 1

        from app.devices.valve_helper import VALVE_TYPES
        device_config = DeviceTypeRegistry.get(type_code)
        is_valve_type = device_config and device_config.code in VALVE_TYPES
        if is_valve_type and sr.accessories:
            db.session.flush()
            for record, acc_group in zip(sr.records, sr.accessories):
                if not record.id:
                    continue
                for acc in acc_group:
                    name = acc.get("名称", "")
                    attachment = ValveAttachment(
                        device_type=type_code,
                        device_id=record.id,
                        名称=name,
                        type=_infer_attachment_type(name),
                        型号规格=acc.get("型号规格", ""),
                        生产厂家=acc.get("生产厂家", ""),
                        设备等级=acc.get("设备等级", ""),
                    )
                    db.session.add(attachment)

        per_sheet.append({"sheet": sheet_name, "created": created, "skipped": skipped, "updated": updated, "skipped_sheet": False})
        total_created += created
        total_skipped += skipped
        total_updated += updated

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

    parts = [f"创建 {total_created} 条"]
    if total_skipped:
        parts.append(f"跳过 {total_skipped} 条")
    if total_updated:
        parts.append(f"更新 {total_updated} 条")
    flash(f"导入完成：{'，'.join(parts)}")
    return redirect(url_for("imports.index"))
```

- [ ] **Step 2: 运行现有测试确认没破坏**

Run: `cd /d E:\项目服务\value\InstrumentValveLedgerSystem && .venv\Scripts\pytest tests/ -v --timeout=30`
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add app/routes/imports.py
git commit -m "feat: 导入执行支持跳过/覆盖/中止三种去重模式"
```

---

### Task 6: 清理 — 移除旧的 has_duplicate_tag 引用

**Files:**
- Modify: `app/devices/valve_helper.py` (移除 has_duplicate_tag，如不再被引用)
- Verify: 检查 `has_duplicate_tag` 的所有引用

- [ ] **Step 1: 检查 has_duplicate_tag 是否还有引用**

Run: `cd /d E:\项目服务\value\InstrumentValveLedgerSystem && grep -rn "has_duplicate_tag" app/`
Expected: 可能在 valve_helper.py 的定义和被替换的 ledgers.py 中出现

- [ ] **Step 2: 如无其他引用，移除 has_duplicate_tag 函数**

```python
# 从 valve_helper.py 中删除 has_duplicate_tag 函数定义（约 73-81 行）
```

- [ ] **Step 3: 运行测试确认**

Run: `cd /d E:\项目服务\value\InstrumentValveLedgerSystem && .venv\Scripts\pytest tests/ -v --timeout=30`
Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add app/devices/valve_helper.py
git commit -m "refactor: 移除旧的 has_duplicate_tag，统一使用 check_duplicate"
```
