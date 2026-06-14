# Sheet 映射记忆功能 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 让系统记住用户手动选择的 Sheet → 设备类型映射，下次同一 Sheet 名自动应用。

**架构:** 新增 `SheetMapping` 数据库表 + 在 imports.py 路由层增加记忆查填逻辑 + 管理员独立页面管理。

**技术栈:** Flask、SQLAlchemy、Jinja2、pytest

---

### Task 1: 新增 SheetMapping 模型

**文件:**
- Modify: `app/models.py` (在 Setting 类之后追加)

- [ ] **Step 1: 追加 SheetMapping 模型到 models.py 末尾**

在 `app/models.py` 第 221 行（Setting 类末尾）之后追加：

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

- [ ] **Step 2: 验证模型加载**

Run: `python -c "from app.models import SheetMapping; print('OK')"`
Expected: 打印 OK

- [ ] **Step 3: 提交**

```bash
git add -A && git commit -m "feat: add SheetMapping model for import mapping memory"
```

---

### Task 2: upload() 中查记忆表自动填充

**文件:**
- Modify: `app/routes/imports.py` (upload 函数，第 114-131 行)

- [ ] **Step 1: 在 upload() 中插入查表逻辑**

在 `imports.py:114`（`preview, unmatched = _build_preview(result)`）之后，`if unmatched:`（当前第 121 行）之前，插入：

```python
    # 查记忆表，自动填充已学习的映射
    if unmatched:
        existing = SheetMapping.query.filter(
            SheetMapping.sheet_name.in_(unmatched)
        ).all()
        auto_mappings = {m.sheet_name: m.type_code for m in existing}
        new_unmatched = []
        for name in unmatched:
            if name in auto_mappings:
                if "import_mappings" not in session:
                    session["import_mappings"] = {}
                session["import_mappings"][name] = auto_mappings[name]
            else:
                new_unmatched.append(name)
        unmatched = new_unmatched
```

同时需要在文件顶部 import SheetMapping：

```python
from app.models import db, Ledger, Valve, ValveAttachment, SheetMapping
```

- [ ] **Step 2: 验证改动**

检查文件关键部分逻辑正确：
- unmatched 列表在循环后被缩减为 new_unmatched
- 命中者自动填入 session["import_mappings"]
- 未命中者保留弹窗

- [ ] **Step 3: 提交**

```bash
git add -A && git commit -m "feat: auto-fill session mappings from SheetMapping table on upload"
```

---

### Task 3: save_mapping() 持久化到 DB

**文件:**
- Modify: `app/routes/imports.py` (save_mapping 函数，第 190-206 行)

- [ ] **Step 1: 在 save_mapping() 末尾追加持久化逻辑**

当前 `save_mapping()` 第 205 行为：

```python
    session["import_mappings"] = mappings
    return redirect(url_for("imports.preview"))
```

改成：

```python
    session["import_mappings"] = mappings

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

    return redirect(url_for("imports.preview"))
```

- [ ] **Step 2: 提交**

```bash
git add -A && git commit -m "feat: persist manual mappings to SheetMapping table"
```

---

### Task 4: 管理员管理路由

**文件:**
- Modify: `app/routes/admin.py` (在末尾追加)

- [ ] **Step 1: 在 admin.py 末尾追加路由**

在 `app/routes/admin.py` 末尾追加：

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

同时文件顶部 import 追加 SheetMapping：

```python
from app.models import db, User, Setting, SheetMapping
```

- [ ] **Step 2: 提交**

```bash
git add -A && git commit -m "feat: add admin routes for sheet mapping management"
```

---

### Task 5: 管理员管理页面模板

**文件:**
- Create: `templates/admin/sheet_mappings.html`

- [ ] **Step 1: 创建模板文件**

```html
{% extends "base.html" %}

{% block page_title %}Sheet 映射记忆管理{% endblock %}

{% block content %}
<div class="modern-card">
    <div class="card-header-custom d-flex justify-content-between align-items-center">
        <span><i class="bi bi-bookmark"></i> Sheet 映射记忆列表</span>
        <a href="{{ url_for('admin.index') }}" class="btn-back-header">
            <i class="bi bi-arrow-left"></i> 返回管理
        </a>
    </div>
    <div class="card-body-custom">
        <p class="text-muted mb-3">
            系统自动记录用户在导入时手动选择的 Sheet → 设备类型映射。
            下次遇到相同 Sheet 名称时将自动应用，不再弹窗。
        </p>

        {% if mappings %}
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Sheet 名称</th>
                        <th>映射类型</th>
                        <th>创建人</th>
                        <th>创建时间</th>
                        <th>更新时间</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    {% for m in mappings %}
                    <tr>
                        <td><code>{{ m.sheet_name }}</code></td>
                        <td>{{ m.type_code }}</td>
                        <td>{{ m.creator.real_name or m.creator.username }}</td>
                        <td>{{ m.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
                        <td>{{ m.updated_at.strftime('%Y-%m-%d %H:%M') }}</td>
                        <td>
                            <form method="POST"
                                  action="{{ url_for('admin.delete_sheet_mapping', id=m.id) }}"
                                  style="display:inline;"
                                  onsubmit="return confirm('确认删除映射「{{ m.sheet_name }}→{{ m.type_code }}」？')">
                                <button type="submit" class="btn btn-sm btn-danger">
                                    <i class="bi bi-trash"></i> 删除
                                </button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <div class="text-center py-5 text-muted">
            <i class="bi bi-inbox" style="font-size: 48px;"></i>
            <p class="mt-2">暂无映射记录</p>
            <p>用户导入 Excel 时手动选择映射后，记录会出现在这里。</p>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: 提交**

```bash
git add -A && git commit -m "feat: add sheet mapping management template"
```

---

### Task 6: 管理首页添加入口

**文件:**
- Modify: `templates/admin/index.html`

- [ ] **Step 1: 在 stats-grid 区域追加卡片**

在 `templates/admin/index.html:13`（用户管理 stat-card 之后）追加：

```html
    <a href="{{ url_for('admin.sheet_mappings') }}" class="stat-card">
        <div class="stat-icon warning"><i class="bi bi-bookmark"></i></div>
        <div class="stat-content">
            <h3>{{ mappings_count }}</h3>
            <p>Sheet 映射记忆</p>
        </div>
    </a>
```

在 `modern-card` 的功能列表中追加一行（第 41-44 行，设置卡片之后）：

```html
            <div class="col-md-6 mb-3">
                <a href="{{ url_for('admin.sheet_mappings') }}" class="quick-action-btn w-100" style="background: #f8fafc; color: var(--text-dark); border: 1px solid var(--border-color); justify-content: flex-start; padding: 20px;">
                    <div class="stat-icon warning" style="width: 48px; height: 48px; font-size: 20px;"><i class="bi bi-bookmark"></i></div>
                    <div>
                        <div style="font-weight: 600;">Sheet 映射记忆</div>
                        <small class="text-muted">管理导入记忆映射</small>
                    </div>
                </a>
            </div>
```

- [ ] **Step 2: 在 admin.py 同步修改 index 路由传 count**

修改 `admin.py:20-25` 的 `index()`：

```python
@admin.route("/")
@login_required
@require_admin
def index():
    user_count = User.query.filter_by(status="active").count()
    mappings_count = SheetMapping.query.count()
    return render_template(
        "admin/index.html",
        user_count=user_count,
        mappings_count=mappings_count,
    )
```

- [ ] **Step 3: 提交**

```bash
git add -A && git commit -m "feat: add sheet mapping entry to admin index"
```

---

### Task 7: 单元测试

**文件:**
- Create: `tests/import_engine/test_sheet_mapping.py`

- [ ] **Step 1: 编写测试**

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from app import create_app, db
from app.models import User, SheetMapping
from app.import_engine import ImportEngine
from flask import session


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["UPLOAD_FOLDER"] = "/tmp/test_uploads"

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def init_db(app):
    with app.app_context():
        admin = User(username="admin", role="admin", real_name="管理员")
        admin.set_password("admin123")
        db.session.add(admin)
        user = User(username="user1", role="employee", real_name="张三")
        user.set_password("user123")
        db.session.add(user)
        db.session.commit()
        yield db


class TestSheetMapping:
    """SheetMapping 模型测试"""

    def test_create_mapping(self, app, init_db):
        with app.app_context():
            user = User.query.filter_by(username="user1").first()
            m = SheetMapping(
                sheet_name="测试流量",
                type_code="flow_meter",
                created_by=user.id,
            )
            db.session.add(m)
            db.session.commit()

            saved = SheetMapping.query.filter_by(sheet_name="测试流量").first()
            assert saved is not None
            assert saved.type_code == "flow_meter"
            assert saved.created_by == user.id

    def test_unique_sheet_name(self, app, init_db):
        with app.app_context():
            user = User.query.filter_by(username="user1").first()
            m1 = SheetMapping(
                sheet_name="同一Sheet", type_code="flow_meter", created_by=user.id,
            )
            db.session.add(m1)
            db.session.commit()

            m2 = SheetMapping(
                sheet_name="同一Sheet", type_code="valve", created_by=user.id,
            )
            with pytest.raises(Exception):
                db.session.add(m2)
                db.session.commit()

    def test_update_existing_mapping(self, app, init_db):
        with app.app_context():
            user = User.query.filter_by(username="user1").first()
            m = SheetMapping(
                sheet_name="测试", type_code="flow_meter", created_by=user.id,
            )
            db.session.add(m)
            db.session.commit()

            m.type_code = "valve"
            db.session.commit()

            updated = SheetMapping.query.filter_by(sheet_name="测试").first()
            assert updated.type_code == "valve"

    def test_delete_mapping(self, app, init_db):
        with app.app_context():
            user = User.query.filter_by(username="user1").first()
            m = SheetMapping(
                sheet_name="待删除", type_code="temperature", created_by=user.id,
            )
            db.session.add(m)
            db.session.commit()

            db.session.delete(m)
            db.session.commit()

            assert SheetMapping.query.filter_by(sheet_name="待删除").count() == 0

    def test_batch_query(self, app, init_db):
        with app.app_context():
            user = User.query.filter_by(username="user1").first()
            names = ["A", "B", "C", "D"]
            for name in names[:3]:
                db.session.add(SheetMapping(
                    sheet_name=name, type_code="valve", created_by=user.id,
                ))
            db.session.commit()

            result = SheetMapping.query.filter(
                SheetMapping.sheet_name.in_(["A", "B", "X", "Y"])
            ).all()
            assert len(result) == 2

    def test_admin_route_requires_login(self, app, client):
        response = client.get("/admin/sheet-mappings")
        assert response.status_code in (302, 401)

    def test_admin_route_requires_admin_role(self, app, client, init_db):
        with app.app_context():
            user = User.query.filter_by(username="user1").first()
        client.post("/auth/login", data={
            "username": "user1", "password": "user123",
        }, follow_redirects=True)
        response = client.get("/admin/sheet-mappings")
        assert response.status_code == 302

    def test_admin_sheet_mappings_page(self, app, client, init_db):
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            db.session.add(SheetMapping(
                sheet_name="流量计", type_code="flow_meter",
                created_by=admin.id,
            ))
            db.session.commit()

        client.post("/auth/login", data={
            "username": "admin", "password": "admin123",
        }, follow_redirects=True)
        response = client.get("/admin/sheet-mappings")
        assert response.status_code == 200
        assert "流量计" in response.get_data(as_text=True)
        assert "flow_meter" in response.get_data(as_text=True)

    def test_delete_sheet_mapping(self, app, client, init_db):
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            m = SheetMapping(
                sheet_name="待删除映射", type_code="temperature",
                created_by=admin.id,
            )
            db.session.add(m)
            db.session.commit()
            mapping_id = m.id

        client.post("/auth/login", data={
            "username": "admin", "password": "admin123",
        }, follow_redirects=True)
        client.post(f"/admin/sheet-mappings/{mapping_id}/delete")

        with app.app_context():
            assert SheetMapping.query.get(mapping_id) is None
```

- [ ] **Step 2: 运行测试**

```bash
python -m pytest tests/import_engine/test_sheet_mapping.py -v
```

Expected: 所有测试通过

- [ ] **Step 3: 提交**

```bash
git add -A && git commit -m "test: add sheet mapping CRUD and admin route tests"
```
