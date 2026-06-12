# 导入模块集中化设计

## 目标

将所有设备类型的导入功能集中到统一的导入界面 `/imports`，消除散落在 `devices.py` 和 `valves/exports.py` 中的独立导入路由。

## 设计方案

采用方案 A（纯整合）：增强现有 `ImportEngine` 使其包含阀门附件处理，删除分散的独立导入路由，统一走 `/imports` 蓝图的"上传 → 预览 → 确认"流程。

## 具体变更

### 1. 增强 `app/routes/imports.py`

- **`execute()` 路由增加阀门附件处理逻辑**：当检测到当前 sheet 的类型为阀门（`valve`）且有附件数据时，将附件写入 `ValveAttachment` 表，关联到对应的 Valve 记录。
- **自动创建 Ledger**：导入执行时，按 `(类型, 当前用户)` 查找是否已有同类型草稿台账合集。如果不存在则自动创建。如果用户选择了"合并到同类型台账合集"，则同一类型的所有记录归入同一个 Ledger。

### 2. 替换散落的导入路由

| 现有路由 | 变更方式 |
|----------|----------|
| `devices/<type_code>/import` | 改为重定向到 `imports.index`，并添加 flash 提示 |
| `valves/import` | 改为重定向到 `imports.index` |
| `valves/import/execute` | 删除 |
| `devices.py` 中的 `import_data` 函数 | 保留但改为重定向 |

### 3. 添加导航入口

- **侧边栏**：在 `base.html` 的侧边栏中，为员工角色添加"导入数据"菜单项，链接到 `imports.index`。
- **首页**：在 `index_employee.html` 的 stats-grid 中添加导入数据卡片。

### 4. 模板调整

- `imports/import.html`：增强引导说明，突出支持所有设备类型。
- `imports/import_preview.html`：增加每个 sheet 的附件数量显示；阀门类型的附件单独提示。
- 删除不再使用的模板：`devices/import.html`、`valves/import.html`、`valves/import_preview.html`。

### 5. 删除/清理

- `app/routes/devices.py` 中的 `import_data` 函数改为重定向。
- `app/routes/valves/exports.py` 中的 `import_data` 和 `import_execute` 函数删除，对应的路由注册移除。
- `app/routes/valves/import_processor.py` 中的 `process_import_preview` 函数保留（导出功能仍可能引用）。

## 数据流

```
上传 Excel
  → ImportEngine.import_file()
    → SheetClassifier: 识别每个 Sheet 的仪表类型
    → DataExtractor: 提取数据行和附件行
    → ColumnMapper: 列名规范化
    → DataLoader: 创建模型实例（阀门类型不排序，preserve_order=True）
  → 返回 SheetImportResult（含 records + accessories）
  → 预览页面展示各 Sheet 信息
  → 用户确认后 execute():
    → 对每个 Sheet:
      → 查找或创建 Ledger
      → 将 records 写入对应设备表 + 设置 ledger_id
      → 阀门类型：遍历 accessories，写入 ValveAttachment 表并关联到父 Valve
    → 提交事务，清理临时文件
```

## 附件处理

ImportEngine 的 `DataExtractor` 已具备附件行识别能力：数据行中序号为空但其他列有内容的行自动归为附件。

数据关联问题：`DataLoader.create_records` 按 `sequence_no` 对 records 排序，但 accessories 保持原始顺序。附件必须与其父阀门记录正确关联。

解决方案：修改 `DataLoader` 添加 `preserve_order` 参数，阀门类型不排序以保持附件关联性。`execute()` 路由中使用状态机遍历 records 和 accessories。

注意：accessories 存储的是原始提取的字典（keys 为 Excel 原始列名，如"名称""型号规格"），不经过 ColumnMapper 映射。附件类型通过 `_infer_attachment_type` 逻辑从名称推断：

```python
if sr.type_code == "valve" and sr.accessories:
    acc_idx = 0
    for record in sr.records:
        if not hasattr(record, 'id') or not record.id:
            continue
        # 收集当前阀门记录后的所有附件行
        while acc_idx < len(sr.accessories):
            acc = sr.accessories[acc_idx]
            acc_idx += 1
            name = acc.get("名称", "")
            attachment = ValveAttachment(
                valve_id=record.id,
                name=name,
                type=_infer_attachment_type(name),
                model=acc.get("型号规格"),
                manufacturer=acc.get("生产厂家"),
                device_grade=acc.get("设备等级"),
            )
            db.session.add(attachment)


def _infer_attachment_type(name: str) -> str:
    """从附件名称推断类型"""
    keywords = {
        "定位器": ["定位器"], "电磁阀": ["电磁阀"], "过滤器": ["过滤器"],
        "减压阀": ["减压阀"], "保位阀": ["保位阀"], "放大器": ["放大器"],
        "转换器": ["转换器"], "限位开关": ["限位开关"],
    }
    for att_type, kw_list in keywords.items():
        for kw in kw_list:
            if kw in name:
                return att_type
    return name
```

## 导航入口

**侧边栏**（`base.html`，仅在员工角色显示）：

```html
{% if current_user.role == 'employee' %}
<a href="{{ url_for('imports.index') }}" class="sidebar-menu-item {% if request.endpoint == 'imports.index' %}active{% endif %}">
    <i class="bi bi-upload"></i><span>导入数据</span>
</a>
{% endif %}
```

**首页**（`index_employee.html`）：

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

## 需要修改的核心文件

| 文件 | 变更 |
|------|------|
| `app/import_engine/loader.py` | `create_records` 增加 `preserve_order` 参数，阀门类型时不排序 |
| `app/routes/imports.py` | `execute()` 增加附件处理和自动创建 Ledger 逻辑 |
| `app/routes/devices.py` | `import_data` 改为重定向到 `imports.index` |
| `app/routes/valves/exports.py` | 删除 `import_data` 和 `import_execute` 函数及路由注册 |
| `app/__init__.py` | 注册 `imports` 蓝图（当前未注册，需添加 `from app.routes.imports import imports` + `app.register_blueprint(imports)`） |
| `templates/base.html` | 侧边栏添加"导入数据"菜单项（员工角色） |
| `templates/index_employee.html` | 首页添加导入数据卡片 |
| `templates/imports/import.html` | 增强引导说明 |
| `templates/imports/import_preview.html` | 增加附件数量显示 |

## 不涉及的范围

- 导出功能保持不变。
- 审批流程不变。
- 设备类型注册机制不变。
