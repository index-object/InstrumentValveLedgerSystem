# 导入模块 Sheet 映射记忆功能设计

**日期**: 2026-06-14  
**状态**: 待实现

---

## 概述

当用户上传 Excel 文件，系统无法自动识别某个 Sheet 的设备类型时，用户手动选择映射后，系统应记住该选择。下次再遇到相同 Sheet 名称时自动应用，不再弹窗。

## 需求规格

| 维度 | 决定 |
|------|------|
| 匹配粒度 | Sheet 名称**精确匹配** |
| 作用范围 | **全局共享**（所有用户复用） |
| 命中行为 | **静默应用**，不弹窗 |
| 管理方式 | **管理员独立页面**，可查看/删除 |
| 更新策略 | 同一 sheet_name 重复映射时**覆盖**更新 |

---

## 架构设计

```
上传 Excel
    ↓
引擎处理 → 分类器识别失败 → 收集 unmatched 列表
    ↓
查 SheetMapping 表（sheet_name IN unmatched）
    ↓
命中 → 自动填充 session["import_mappings"]，从 unmatched 移除
未命中 → 仍弹窗让用户手动选择
    ↓
用户提交手动映射 → 写 session + 写 SheetMapping 表
    ↓
执行导入 → 从 session 读取映射（不变）
```

### 涉及文件

| 文件 | 改动类型 |
|------|----------|
| `app/models.py` | 新增 `SheetMapping` 模型 |
| `app/routes/imports.py` | 修改 `upload()` 和 `save_mapping()` |
| `app/routes/admin.py` | 新增 `sheet_mappings` 管理路由 |
| `templates/admin/sheet_mappings.html` | 新增管理页面 |
| `templates/admin/index.html` | 新增入口链接 |

### 不动

- `app/import_engine/classifier.py` — 分类器不改
- `app/import_engine/mapper.py` — 映射器不改
- `app/import_engine/engine.py` — 引擎不改
- `app/import_engine/config/types.yaml` — 类型配置不改
- `templates/imports/import.html` — 前端弹窗不改

---

## 数据库模型

### SheetMapping

```python
class SheetMapping(db.Model):
    __tablename__ = "sheet_mappings"

    id = db.Column(db.Integer, primary_key=True)
    sheet_name = db.Column(db.String(200), unique=True, nullable=False)
    type_code = db.Column(db.String(50), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    creator = db.relationship("User", foreign_keys=[created_by])
```

---

## 路由层改动

### imports.py — upload()

```python
# 第114行后，_build_preview 拿到 unmatched 列表后
preview, unmatched = _build_preview(result)

# ★ 新增：查记忆表自动填充
if unmatched:
    existing = SheetMapping.query.filter(
        SheetMapping.sheet_name.in_(unmatched)
    ).all()
    auto_mappings = {}
    for m in existing:
        auto_mappings[m.sheet_name] = m.type_code

    # 命中者从 unmatched 移除，自动填入 session
    new_unmatched = []
    for name in unmatched:
        if name in auto_mappings:
            if "import_mappings" not in session:
                session["import_mappings"] = {}
            session["import_mappings"][name] = auto_mappings[name]
        else:
            new_unmatched.append(name)
    unmatched = new_unmatched

# 原有逻辑不变：如果仍有 unmatched 则弹窗，否则跳 preview
```

### imports.py — save_mapping()

```python
# 第203行，写 session 后新增
session["import_mappings"] = mappings

# ★ 新增：持久化到 SheetMapping 表
for sheet_name, type_code in mappings.items():
    existing = SheetMapping.query.filter_by(sheet_name=sheet_name).first()
    if existing:
        existing.type_code = type_code
        existing.updated_at = datetime.utcnow()
    else:
        mapping = SheetMapping(
            sheet_name=sheet_name,
            type_code=type_code,
            created_by=current_user.id,
        )
        db.session.add(mapping)
db.session.commit()
```

### imports.py — execute()

不变，仍从 `session["import_mappings"]` 读取映射。记忆表只在 upload 和 save_mapping 阶段介入。

---

## 管理页面

### 路由 — admin.py

```python
@admin.route("/sheet-mappings")
@login_required
@require_admin
def sheet_mappings():
    mappings = SheetMapping.query.order_by(
        SheetMapping.updated_at.desc()
    ).all()
    return render_template(
        "admin/sheet_mappings.html",
        mappings=mappings,
    )


@admin.route("/sheet-mappings/<int:id>/delete", methods=["POST"])
@login_required
@require_admin
def delete_sheet_mapping(id):
    mapping = SheetMapping.query.get_or_404(id)
    db.session.delete(mapping)
    db.session.commit()
    flash(f"已删除映射: {mapping.sheet_name} → {mapping.type_code}")
    return redirect(url_for("admin.sheet_mappings"))
```

### 模板 — templates/admin/sheet_mappings.html

- 表格展示：Sheet名称、映射类型、创建人、创建时间、更新时间
- 每行有删除按钮（POST 确认）
- 空状态提示
- 与管理后台现有风格一致（Bootstrap + modern-card）

### 入口

在 `templates/admin/index.html` 管理后台首页增加一个卡片入口"Sheet 映射记忆管理"。

---

## 数据流验证

| 场景 | 预期行为 |
|------|----------|
| 首次上传 "流量" Sheet | 弹窗，用户选"流量计" → 写 session + 写 DB |
| 再次上传 "流量" Sheet | 查 DB 命中 → 自动填充 session，不弹窗 |
| 用户删除映射后上传 "流量" | DB 无记录 → 弹窗 |
| 用户上传 "远传流量" Sheet | 精确匹配不命中 → 弹窗 |
| 用户重复映射 "流量" → "压力变送器" | DB 记录更新，下次按新映射 |
| Leader 创建的映射 | Admin 也能在管理页看到和删除 |
