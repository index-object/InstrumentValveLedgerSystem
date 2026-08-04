# 年度阀门检修计划 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现领导发布检修计划、员工查看预警并关联维护记录推进进度的完整功能。

**Architecture:** 新增 `plans_bp` 蓝图（单文件 `app/routes/plans.py`）处理计划 CRUD + 通知，新增 3 个模型（MaintenancePlan、MaintenancePlanItem、Notification），扩展现有维护记录路由以支持 plan_item_id 关联。前端新增 `templates/plans/` 模板目录。

**Tech Stack:** Flask, SQLAlchemy, Jinja2 (与项目现有技术栈一致)

## Global Constraints

- 仅从已审批（status=approved）阀门中选择计划项
- 计划状态机：draft → published → archived
- 计划项状态：pending / completed / overdue（overdue 在查询时计算，不持久化）
- 发布计划时向所有 employee+admin 角色用户创建通知
- 维护记录创建时通过 plan_item_id 关联计划项，自动更新计划项状态和计划进度
- 不引入定时任务、不引入周期性自动生成

---

### Task 1: Database Models

**Files:**
- Modify: `app/models.py` — 末尾追加 3 个模型

- [ ] **Step 1: Add MaintenancePlan model**

在 `app/models.py` 末尾追加：

```python
class MaintenancePlan(db.Model):
    __tablename__ = "maintenance_plans"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="draft")
    total_items = db.Column(db.Integer, default=0)
    completed_items = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    published_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship("User", foreign_keys=[created_by])
    publisher = db.relationship("User", foreign_keys=[published_by])
    items = db.relationship("MaintenancePlanItem", backref="plan", lazy="dynamic",
                            cascade="all, delete-orphan",
                            order_by="MaintenancePlanItem.planned_date_start")
```

- [ ] **Step 2: Add MaintenancePlanItem model**

```python
class MaintenancePlanItem(db.Model):
    __tablename__ = "maintenance_plan_items"
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("maintenance_plans.id"), nullable=False)
    device_type = db.Column(db.String(20), nullable=False)
    device_id = db.Column(db.Integer, nullable=False)
    tag = db.Column(db.String(50), nullable=False)
    device_name = db.Column(db.String(100))
    planned_date_start = db.Column(db.Date, nullable=False)
    planned_date_end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    maintenance_id = db.Column(db.Integer, db.ForeignKey("maintenance_records.id"))
    completed_at = db.Column(db.DateTime)
    completed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    maintenance_record = db.relationship("MaintenanceRecord")
    completer = db.relationship("User", foreign_keys=[completed_by])
```

- [ ] **Step 3: Add Notification model**

```python
class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    ref_type = db.Column(db.String(20))
    ref_id = db.Column(db.Integer)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="notifications")
```

- [ ] **Step 4: Create database tables**

```bash
cd /home/mrg/work/InstrumentValveLedgerSystem
uv run python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
    print('Tables created successfully')
"
```

- [ ] **Step 5: Verify tables exist**

```bash
cd /home/mrg/work/InstrumentValveLedgerSystem
uv run python -c "
from app import create_app, db
from app.models import MaintenancePlan, MaintenancePlanItem, Notification
app = create_app()
with app.app_context():
    assert MaintenancePlan.__table__.exists(db.engine)
    assert MaintenancePlanItem.__table__.exists(db.engine)
    assert Notification.__table__.exists(db.engine)
    print('All tables verified')
"
```

- [ ] **Step 6: Commit**

```bash
cd /home/mrg/work/InstrumentValveLedgerSystem
git add app/models.py
git commit -m "feat: add MaintenancePlan, MaintenancePlanItem, Notification models"
```

---

### Task 2: Plan Blueprint + Basic CRUD Routes

**Files:**
- Create: `app/routes/plans.py`
- Modify: `app/__init__.py` — 注册 blueprint

- [ ] **Step 1: Create `app/routes/plans.py` with blueprint + 上下文处理器**

```python
from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, jsonify,
)
from flask_login import login_required, current_user
from app.models import db, MaintenancePlan, MaintenancePlanItem, Notification, User
from app.devices.valve_helper import get_valve_model, get_valve_ledger_type, get_all_valve_models
from app.devices import DeviceTypeRegistry
from datetime import datetime, date
from sqlalchemy import or_

plans_bp = Blueprint("plans", __name__, url_prefix="")


@plans_bp.context_processor
def inject_plan_nav():
    if current_user.is_authenticated:
        now = date.today()
        # 员工端预警计数
        warning_count = 0
        if current_user.role in ("employee", "admin"):
            from app.models import MaintenancePlan, MaintenancePlanItem
            published_plan_ids = db.session.query(MaintenancePlan.id).filter(
                MaintenancePlan.status == "published"
            ).subquery()
            warning_count = MaintenancePlanItem.query.filter(
                MaintenancePlanItem.plan_id.in_(published_plan_ids),
                MaintenancePlanItem.status == "pending",
                MaintenancePlanItem.planned_date_end >= now.isoformat(),
                MaintenancePlanItem.planned_date_end <= (date(now.year, now.month, now.day + 7).isoformat()),
            ).count() + MaintenancePlanItem.query.filter(
                MaintenancePlanItem.plan_id.in_(published_plan_ids),
                MaintenancePlanItem.status == "pending",
                MaintenancePlanItem.planned_date_end < now.isoformat(),
            ).count()
        return dict(plan_warning_count=warning_count)
    return dict(plan_warning_count=0)
```

- [ ] **Step 2: Implement `index` (list)**

```python
@plans_bp.route("/plans")
@login_required
def index():
    query = MaintenancePlan.query
    if current_user.role == "employee":
        query = query.filter(MaintenancePlan.status.in_(["published", "archived"]))
    search = request.args.get("search")
    status_filter = request.args.get("status")
    if search:
        query = query.filter(MaintenancePlan.title.contains(search))
    if status_filter:
        query = query.filter(MaintenancePlan.status == status_filter)
    plans = query.order_by(MaintenancePlan.created_at.desc()).all()

    # 计算每个计划的实时进度
    now = date.today()
    for p in plans:
        items = MaintenancePlanItem.query.filter_by(plan_id=p.id).all()
        completed = sum(1 for i in items if i.status == "completed")
        overdue = sum(1 for i in items if i.status == "pending" and i.planned_date_end < now)
        p._completed = completed
        p._overdue = overdue
        p._total = len(items)

    stats = {
        "total": len(plans),
        "draft": sum(1 for p in plans if p.status == "draft"),
        "published": sum(1 for p in plans if p.status == "published"),
        "archived": sum(1 for p in plans if p.status == "archived"),
    }
    return render_template("plans/list.html", plans=plans, stats=stats)
```

- [ ] **Step 3: Implement `create`**

```python
@plans_bp.route("/plan/new", methods=["GET", "POST"])
@login_required
def create():
    if current_user.role not in ("leader", "admin"):
        flash("无权创建检修计划")
        return redirect(url_for("plans.index"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("请输入计划标题")
            return render_template("plans/form.html")
        plan = MaintenancePlan(
            title=title,
            description=request.form.get("description", "").strip(),
            created_by=current_user.id,
        )
        db.session.add(plan)
        db.session.commit()
        flash("计划已保存为草稿")
        return redirect(url_for("plans.detail", id=plan.id))

    return render_template("plans/form.html")
```

- [ ] **Step 4: Implement `detail`**

```python
@plans_bp.route("/plan/<int:id>")
@login_required
def detail(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role == "employee" and plan.status not in ("published", "archived"):
        flash("无权查看此计划")
        return redirect(url_for("plans.index"))

    now = date.today()
    items = MaintenancePlanItem.query.filter_by(plan_id=plan.id).order_by(
        MaintenancePlanItem.planned_date_start
    ).all()

    for item in items:
        if item.status == "pending" and item.planned_date_end < now:
            item._overdue = True
        else:
            item._overdue = False

    # 获取所有已审批阀门用于"添加阀门"弹窗
    approved_devices = []
    for model in get_all_valve_models():
        for v in model.query.filter(model.status == "approved").order_by(model.位号).all():
            approved_devices.append({
                "id": v.id,
                "type": get_valve_ledger_type(v),
                "tag": v.位号,
                "name": v.名称 or "",
                "unit": v.装置名称 or "",
            })
    # 非阀门设备
    for config in DeviceTypeRegistry._configs.values():
        if config.model_class:
            for d in config.model_class.query.filter(config.model_class.status == "approved").order_by(config.model_class.位号).all():
                approved_devices.append({
                    "id": d.id,
                    "type": config.type_code,
                    "tag": d.位号,
                    "name": d.名称 or "",
                    "unit": d.装置名称 or "",
                })

    return render_template("plans/detail.html", plan=plan, items=items, approved_devices=approved_devices)
```

- [ ] **Step 5: Register blueprint in `app/__init__.py`**

```python
from app.routes.plans import plans_bp
app.register_blueprint(plans_bp)
```

- [ ] **Step 6: Test routes work**

```bash
cd /home/mrg/work/InstrumentValveLedgerSystem
uv run python -c "
from app import create_app
app = create_app()
client = app.test_client()
# Login as leader
with app.test_request_context():
    from flask_login import login_user
    from app.models import User
    with app.app_context():
        user = User.query.filter_by(role='leader').first()
        login_user(user)
    # Can't easily test full flow without session, but at least verify import
    print('Blueprint registered OK')
"
```

- [ ] **Step 7: Commit**

```bash
git add app/routes/plans.py app/__init__.py
git commit -m "feat: add plans blueprint and basic CRUD routes"
```

---

### Task 3: Plan Management Routes (edit, publish, archive, delete, add/remove items)

**Files:**
- Modify: `app/routes/plans.py` — 追加路由
- Create: `app/routes/plans_bp/forms.py` — 可选，但为了简洁直接写在 plans.py 中

- [ ] **Step 1: Implement `edit`**

```python
@plans_bp.route("/plan/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        flash("无权编辑")
        return redirect(url_for("plans.detail", id=id))
    if plan.status != "draft":
        flash("只能编辑草稿状态的计划")
        return redirect(url_for("plans.detail", id=id))

    if request.method == "POST":
        plan.title = request.form.get("title", "").strip() or plan.title
        plan.description = request.form.get("description", "").strip()
        db.session.commit()
        flash("计划已更新")
        return redirect(url_for("plans.detail", id=id))

    return render_template("plans/form.html", plan=plan)
```

- [ ] **Step 2: Implement `publish`**

```python
@plans_bp.route("/plan/<int:id>/publish", methods=["POST"])
@login_required
def publish(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        flash("无权发布")
        return redirect(url_for("plans.detail", id=id))
    if plan.status != "draft":
        flash("只能发布草稿状态的计划")
        return redirect(url_for("plans.detail", id=id))
    if plan.total_items == 0:
        flash("请先添加阀门后再发布")
        return redirect(url_for("plans.detail", id=id))

    plan.status = "published"
    plan.published_by = current_user.id
    plan.published_at = datetime.utcnow()

    # 通知所有 employee 和 admin
    recipients = User.query.filter(User.role.in_(["employee", "admin"]), User.status == "active").all()
    for user in recipients:
        notification = Notification(
            user_id=user.id,
            type="plan_published",
            title=f"新检修计划发布：{plan.title}",
            content=plan.description or f"计划包含 {plan.total_items} 项检修任务，请及时查看并执行。",
            ref_type="plan",
            ref_id=plan.id,
        )
        db.session.add(notification)

    db.session.commit()
    flash(f"计划已发布，已通知 {len(recipients)} 位用户")
    return redirect(url_for("plans.detail", id=id))
```

- [ ] **Step 3: Implement `archive` and `delete`**

```python
@plans_bp.route("/plan/<int:id>/archive", methods=["POST"])
@login_required
def archive(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        flash("无权归档")
        return redirect(url_for("plans.detail", id=id))
    if plan.status != "published":
        flash("只能归档已发布的计划")
        return redirect(url_for("plans.detail", id=id))
    plan.status = "archived"
    db.session.commit()
    flash("计划已归档")
    return redirect(url_for("plans.detail", id=id))


@plans_bp.route("/plan/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        flash("无权删除")
        return redirect(url_for("plans.detail", id=id))
    if plan.status != "draft":
        flash("只能删除草稿状态的计划")
        return redirect(url_for("plans.detail", id=id))
    db.session.delete(plan)
    db.session.commit()
    flash("计划已删除")
    return redirect(url_for("plans.index"))
```

- [ ] **Step 4: Implement `add_items`**

```python
@plans_bp.route("/plan/<int:id>/items/add", methods=["POST"])
@login_required
def add_items(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        return jsonify({"error": "无权操作"}), 403
    if plan.status not in ("draft", "published"):
        return jsonify({"error": "当前状态无法添加阀门"}), 400

    data = request.get_json() or request.form
    devices = data.get("devices", [])
    planned_date_start = data.get("planned_date_start")
    planned_date_end = data.get("planned_date_end")

    added = 0
    for dev in devices:
        device_type = dev.get("type")
        device_id = int(dev.get("id"))
        tag = dev.get("tag", "")
        device_name = dev.get("name", "")

        exists = MaintenancePlanItem.query.filter_by(
            plan_id=plan.id, device_type=device_type, device_id=device_id
        ).first()
        if exists:
            continue

        item = MaintenancePlanItem(
            plan_id=plan.id,
            device_type=device_type,
            device_id=device_id,
            tag=tag,
            device_name=device_name,
            planned_date_start=datetime.strptime(planned_date_start, "%Y-%m-%d").date() if planned_date_start else date.today(),
            planned_date_end=datetime.strptime(planned_date_end, "%Y-%m-%d").date() if planned_date_end else date.today(),
        )
        db.session.add(item)
        added += 1

    plan.total_items = MaintenancePlanItem.query.filter_by(plan_id=plan.id).count()
    db.session.commit()
    return jsonify({"added": added, "total": plan.total_items})
```

- [ ] **Step 5: Implement `remove_item`**

```python
@plans_bp.route("/plan/<int:plan_id>/items/<int:item_id>/remove", methods=["POST"])
@login_required
def remove_item(plan_id, item_id):
    plan = MaintenancePlan.query.get_or_404(plan_id)
    if current_user.role not in ("leader", "admin"):
        flash("无权操作")
        return redirect(url_for("plans.detail", id=plan_id))
    if plan.status not in ("draft", "published"):
        flash("当前状态无法移除阀门")
        return redirect(url_for("plans.detail", id=plan_id))

    item = MaintenancePlanItem.query.get_or_404(item_id)
    if item.plan_id != plan.id:
        abort(404)
    if item.status == "completed":
        flash("已完成项不能移除")
        return redirect(url_for("plans.detail", id=plan_id))

    db.session.delete(item)
    plan.total_items = MaintenancePlanItem.query.filter_by(plan_id=plan.id).count()
    if item.status == "completed":
        plan.completed_items = MaintenancePlanItem.query.filter_by(plan_id=plan.id, status="completed").count()
    db.session.commit()
    flash("阀门已从计划中移除")
    return redirect(url_for("plans.detail", id=plan_id))
```

- [ ] **Step 6: Test 各路由可访问**

```bash
cd /home/mrg/work/InstrumentValveLedgerSystem
uv run python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.routes.plans import plans_bp
    rules = [rule for rule in app.url_map.iter_rules() if 'plan' in rule.rule]
    for r in sorted(rules, key=lambda x: x.rule):
        print(f'{r.methods - {\"OPTIONS\", \"HEAD\"}} {r.rule}')
"
```

- [ ] **Step 7: Commit**

```bash
git add app/routes/plans.py
git commit -m "feat: implement plan publish, archive, delete, item management"
```

---

### Task 4: Plan Templates (list, form, detail)

**Files:**
- Create: `templates/plans/list.html`
- Create: `templates/plans/form.html`
- Create: `templates/plans/detail.html`

参考 `design-prototypes/` 下的静态原型，使用项目已有的 `.cmp-*` CSS 组件。

- [ ] **Step 1: Create `templates/plans/list.html`**

```html
{% extends "base.html" %}
{% block page_title %}检修计划{% endblock %}
{% block header_actions %}
{% if current_user.role in ['leader', 'admin'] %}
<a href="{{ url_for('plans.create') }}" class="cmp-btn cmp-btn--primary"><i class="bi bi-plus-lg"></i> 新建计划</a>
{% endif %}
{% endblock %}

{% block content %}
<!-- 统计卡片行 -->
<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px;">
  <div class="cmp-stat info"><div class="stat-icon info"><i class="bi bi-calendar-check"></i></div><div class="stat-content"><h3>全部计划</h3><p><span class="stat-value">{{ stats.total }}</span> 个</p></div></div>
  <div class="cmp-stat primary"><div class="stat-icon primary"><i class="bi bi-pencil-square"></i></div><div class="stat-content"><h3>草稿</h3><p><span class="stat-value">{{ stats.draft }}</span> 个</p></div></div>
  <div class="cmp-stat success"><div class="stat-icon success"><i class="bi bi-check-circle"></i></div><div class="stat-content"><h3>已发布</h3><p><span class="stat-value">{{ stats.published }}</span> 个</p></div></div>
  <div class="cmp-stat"><div class="stat-icon" style="background: #f1f5f9; color: #475569;"><i class="bi bi-archive"></i></div><div class="stat-content"><h3>已归档</h3><p><span class="stat-value">{{ stats.archived }}</span> 个</p></div></div>
</div>

<!-- 筛选 -->
<div class="cmp-toolbar cmp-toolbar--card" style="margin-bottom: 16px;">
  <div class="cmp-toolbar__left">
    <select class="cmp-toolbar-filter cmp-select" style="width: auto; min-width: 120px;" onchange="location.href=this.dataset.baseUrl + '?status=' + this.value" data-base-url="{{ url_for('plans.index') }}">
      <option value="">全部状态</option>
      <option value="draft" {% if request.args.get('status') == 'draft' %}selected{% endif %}>草稿</option>
      <option value="published" {% if request.args.get('status') == 'published' %}selected{% endif %}>已发布</option>
      <option value="archived" {% if request.args.get('status') == 'archived' %}selected{% endif %}>已归档</option>
    </select>
    <form method="get" class="d-flex gap-2 align-items-center" style="margin:0;">
      <div class="cmp-toolbar-search">
        <i class="bi bi-search"></i>
        <input type="text" name="search" placeholder="搜索计划标题..." value="{{ request.args.get('search', '') }}">
      </div>
      <button type="submit" class="cmp-toolbar-btn cmp-toolbar-btn--primary btn-sm"><i class="bi bi-search"></i></button>
    </form>
  </div>
</div>

<!-- 计划卡片列表 -->
<div style="display: flex; flex-direction: column; gap: 16px;">
{% for plan in plans %}
<div class="cmp-card" style="padding: 0; overflow: hidden;{% if plan.status == 'archived' %} opacity: 0.7;{% endif %}">
  <div style="padding: 20px 24px; display: flex; justify-content: space-between; align-items: flex-start;">
    <div style="flex: 1;">
      <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
        {% if plan.status == 'draft' %}
        <span class="cmp-badge cmp-badge--draft"><i class="bi bi-pencil"></i> 草稿</span>
        {% elif plan.status == 'published' %}
        <span class="cmp-badge cmp-badge--approved"><i class="bi bi-check-circle-fill"></i> 已发布</span>
        {% elif plan.status == 'archived' %}
        <span class="cmp-badge" style="background: #f1f5f9; color: #64748b;"><i class="bi bi-archive-fill"></i> 已归档</span>
        {% endif %}
        <span style="font-size: 18px; font-weight: 600;">{{ plan.title }}</span>
      </div>
      {% if plan.description %}
      <p style="font-size: 14px; color: var(--color-text-muted); margin: 0 0 8px;">{{ plan.description[:80] }}{% if plan.description|length > 80 %}...{% endif %}</p>
      {% endif %}
      <div style="display: flex; gap: 24px; font-size: 13px; color: var(--color-text-muted);">
        <span><i class="bi bi-calendar3"></i> {{ plan.created_at.strftime('%Y-%m-%d') }}</span>
        <span><i class="bi bi-person"></i> {{ plan.creator.real_name or plan.creator.username }}</span>
        <span><i class="bi bi-list-check"></i> {{ plan.total_items }} 项</span>
      </div>
    </div>
    {% if plan.status == 'published' %}
    <div style="min-width: 180px; display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
      <div style="display: flex; align-items: center; gap: 8px; width: 100%;">
        <span style="font-size: 12px; color: var(--color-text-muted);">进度</span>
        <div style="flex: 1; height: 8px; background: var(--gray-200); border-radius: 4px; overflow: hidden;">
          {% set pct = (plan._completed / plan._total * 100) if plan._total > 0 else 0 %}
          <div style="width: {{ pct }}%; height: 100%; background: linear-gradient(90deg, #10b981, #34d399); border-radius: 4px;"></div>
        </div>
        <span style="font-size: 13px; font-weight: 600; color: #059669;">{{ '%.0f'|format(pct) }}%</span>
      </div>
      <div style="display: flex; gap: 16px; font-size: 12px;">
        <span><span style="font-weight: 600;">{{ plan._completed }}</span> 已完成</span>
        <span><span style="font-weight: 600;">{{ plan._total - plan._completed - plan._overdue }}</span> 待办</span>
        {% if plan._overdue > 0 %}<span><span style="font-weight: 600; color: var(--color-danger);">{{ plan._overdue }}</span> 逾期</span>{% endif %}
      </div>
    </div>
    {% endif %}
  </div>
  <div style="border-top: 1px solid var(--color-border); padding: 10px 24px; background: #fafbfc; display: flex; gap: 8px; justify-content: flex-end;">
    <a href="{{ url_for('plans.detail', id=plan.id) }}" class="cmp-toolbar-btn cmp-toolbar-btn--primary"><i class="bi bi-eye"></i> 查看详情</a>
    {% if plan.status == 'draft' and current_user.role in ['leader', 'admin'] %}
    <a href="{{ url_for('plans.edit', id=plan.id) }}" class="cmp-toolbar-btn cmp-toolbar-btn--secondary"><i class="bi bi-pencil"></i> 编辑</a>
    <form method="POST" action="{{ url_for('plans.publish', id=plan.id) }}" style="display:inline;" onsubmit="return confirm('发布后所有员工将收到通知，确认发布？')">
      <button class="cmp-toolbar-btn cmp-toolbar-btn--success"><i class="bi bi-send"></i> 发布</button>
    </form>
    <form method="POST" action="{{ url_for('plans.delete', id=plan.id) }}" style="display:inline;" onsubmit="return confirm('确认删除？')">
      <button class="cmp-toolbar-btn cmp-toolbar-btn--danger"><i class="bi bi-trash"></i> 删除</button>
    </form>
    {% elif plan.status == 'published' and current_user.role in ['leader', 'admin'] %}
    <form method="POST" action="{{ url_for('plans.archive', id=plan.id) }}" style="display:inline;">
      <button class="cmp-toolbar-btn cmp-toolbar-btn--secondary"><i class="bi bi-archive"></i> 归档</button>
    </form>
    {% endif %}
  </div>
</div>
{% else %}
<div class="cmp-empty"><i class="bi bi-calendar-check"></i><p>暂无检修计划</p></div>
{% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 2: Create `templates/plans/form.html`**

```html
{% extends "base.html" %}
{% block page_title %}{{ '编辑计划' if plan else '新建计划' }}{% endblock %}
{% block header_actions %}
<a href="{{ url_for('plans.index') }}" class="cmp-btn cmp-btn--secondary"><i class="bi bi-arrow-left"></i> 返回</a>
{% endblock %}
{% block content %}
<div style="max-width: 800px; margin: 0 auto;">
  <div class="cmp-form-section">
    <div class="cmp-form-section__header"><i class="bi bi-info-circle"></i><h5>基本信息</h5></div>
    <div class="cmp-form-section__body">
      <form method="POST">
        <div class="cmp-field-row">
          <div class="cmp-field">
            <label class="cmp-label"><span class="required">*</span> 计划标题</label>
            <input type="text" name="title" class="cmp-input" value="{{ plan.title if plan else '' }}" placeholder="例如：2026年度大检修计划" required>
          </div>
        </div>
        <div class="cmp-field-row">
          <div class="cmp-field">
            <label class="cmp-label">计划描述</label>
            <textarea name="description" class="cmp-input" rows="4" placeholder="描述本次检修的范围、目的等">{{ plan.description if plan else '' }}</textarea>
          </div>
        </div>
        <div class="d-flex gap-2">
          <button type="submit" class="cmp-btn cmp-btn--primary"><i class="bi bi-save"></i> {{ '保存' if plan else '保存为草稿' }}</button>
          <a href="{{ url_for('plans.index') }}" class="cmp-btn cmp-btn--secondary">取消</a>
        </div>
      </form>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Create `templates/plans/detail.html`**

详情页包含：计划信息、进度看板、计划项列表、添加阀门弹窗。参考 `design-prototypes/plans-detail.html`。

主要结构：
- 顶部：返回按钮 + 标题 + 状态badge + 操作按钮
- 基本信息卡片（描述/创建人/时间）
- 进度概览（环形进度图 + 已完成/待办/逾期统计卡片）
- 计划项表格（搜索/筛选 + 表格列：位号、设备名称、计划起止、状态、关联维护、操作）
- 添加阀门弹窗（搜索/筛选 + 选择阀门 + 批量设置日期）

直接生成完整的模板内容：

```html
{% extends "base.html" %}
{% block page_title %}{{ plan.title }}{% endblock %}
{% block back_btn %}
<a href="{{ url_for('plans.index') }}" class="btn-back-header"><i class="bi bi-arrow-left"></i> 返回</a>
{% endblock %}
{% block header_actions %}
<span class="cmp-badge {% if plan.status == 'published' %}cmp-badge--approved{% elif plan.status == 'draft' %}cmp-badge--draft{% else %}cmp-badge--draft{% endif %}">
  {% if plan.status == 'draft' %}<i class="bi bi-pencil"></i> 草稿
  {% elif plan.status == 'published' %}<i class="bi bi-check-circle-fill"></i> 已发布
  {% else %}<i class="bi bi-archive-fill"></i> 已归档{% endif %}
</span>
{% if current_user.role in ['leader', 'admin'] and plan.status == 'draft' %}
<a href="{{ url_for('plans.edit', id=plan.id) }}" class="cmp-btn cmp-btn--secondary cmp-btn--sm"><i class="bi bi-pencil"></i> 编辑</a>
<form method="POST" action="{{ url_for('plans.publish', id=plan.id) }}" style="display:inline;" onsubmit="return confirm('发布后所有员工将收到通知，确认发布？')">
  <button class="cmp-btn cmp-btn--primary cmp-btn--sm"><i class="bi bi-send"></i> 发布</button>
</form>
{% elif current_user.role in ['leader', 'admin'] and plan.status == 'published' %}
<form method="POST" action="{{ url_for('plans.archive', id=plan.id) }}" style="display:inline;">
  <button class="cmp-btn cmp-btn--secondary cmp-btn--sm"><i class="bi bi-archive"></i> 归档</button>
</form>
{% endif %}
{% endblock %}

{% block content %}
<div style="max-width: 1200px; margin: 0 auto;">

  <!-- 基本信息 -->
  <div class="cmp-card" style="padding: 24px; margin-bottom: 24px;">
    <div style="display: grid; grid-template-columns: auto 1fr; gap: 12px 40px; font-size: 14px;">
      {% if plan.description %}
      <span style="color: var(--color-text-muted);">描述</span><span>{{ plan.description }}</span>
      {% endif %}
      <span style="color: var(--color-text-muted);">创建人</span>
      <span><span class="cmp-creator cmp-creator--0"><span class="cmp-creator__avatar">{{ plan.creator.real_name[0] }}</span>{{ plan.creator.real_name or plan.creator.username }}</span></span>
      <span style="color: var(--color-text-muted);">创建时间</span><span>{{ plan.created_at.strftime('%Y-%m-%d %H:%M') }}</span>
      {% if plan.published_at %}
      <span style="color: var(--color-text-muted);">发布时间</span><span>{{ plan.published_at.strftime('%Y-%m-%d %H:%M') }}（发布人：{{ plan.publisher.real_name or plan.publisher.username }}）</span>
      {% endif %}
    </div>
  </div>

  {% if plan.status == 'published' %}
  <!-- 进度概览 -->
  <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 24px; margin-bottom: 24px;">
    <div class="cmp-card" style="padding: 24px; display: flex; flex-direction: column; align-items: center; justify-content: center;">
      {% set completed = items|selectattr('status', 'equalto', 'completed')|list|length %}
      {% set total = items|length %}
      {% set pct = (completed / total * 100) if total > 0 else 0 %}
      {% set now = ''|string|datetime_format_short %}
      {% set overdue = items|selectattr('_overdue', 'equalto', true)|list|length %}
      <div style="position: relative; width: 140px; height: 140px;">
        <canvas id="progressChart" width="140" height="140"></canvas>
        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center;">
          <span style="font-size: 28px; font-weight: 700; color: #059669;">{{ '%.0f'|format(pct) }}%</span>
          <div style="font-size: 12px; color: var(--color-text-muted);">完成率</div>
        </div>
      </div>
    </div>
    <div class="cmp-card" style="padding: 24px;">
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
        <div style="text-align: center; padding: 20px 16px; background: #f0fdf4; border-radius: 12px;">
          <i class="bi bi-check-circle-fill" style="font-size: 28px; color: #10b981;"></i>
          <div style="font-size: 28px; font-weight: 700; color: #065f46; margin: 8px 0 4px;">{{ completed }}</div>
          <div style="font-size: 13px; color: #065f46;">已完成</div>
        </div>
        <div style="text-align: center; padding: 20px 16px; background: #fffbeb; border-radius: 12px;">
          <i class="bi bi-clock" style="font-size: 28px; color: #f59e0b;"></i>
          <div style="font-size: 28px; font-weight: 700; color: #92400e; margin: 8px 0 4px;">{{ total - completed - overdue }}</div>
          <div style="font-size: 13px; color: #92400e;">待办</div>
        </div>
        {% if overdue > 0 %}
        <div style="text-align: center; padding: 16px; background: #fef2f2; border-radius: 12px; grid-column: 1 / -1;">
          <i class="bi bi-exclamation-triangle-fill" style="font-size: 22px; color: #ef4444;"></i>
          <div style="font-size: 22px; font-weight: 700; color: #991b1b; margin: 4px 0 0;">{{ overdue }}</div>
          <div style="font-size: 13px; color: #991b1b;">已逾期</div>
        </div>
        {% endif %}
      </div>
    </div>
  </div>
  {% endif %}

  <!-- 计划项列表 -->
  <div class="cmp-card" style="padding: 0; overflow: hidden;">
    <div style="padding: 16px 24px; border-bottom: 1px solid var(--color-border); display: flex; justify-content: space-between; align-items: center;">
      <div style="display: flex; align-items: center; gap: 12px;">
        <h5 style="margin: 0; font-size: 16px; font-weight: 600;">计划项</h5>
        <span class="cmp-badge" style="background: #f1f5f9; color: #475569; font-size: 12px;">共 {{ items|length }} 项</span>
      </div>
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <div class="cmp-toolbar-search">
          <i class="bi bi-search"></i>
          <input type="text" id="itemSearch" placeholder="搜索位号..." style="padding-left: 32px; height: 36px; width: 180px; font-size: 13px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--gray-50);">
        </div>
        <select id="itemStatusFilter" class="cmp-select" style="width: auto; min-width: 100px; height: 36px; font-size: 13px;">
          <option value="">全部</option>
          <option value="pending">待办</option>
          <option value="completed">已完成</option>
          <option value="overdue">已逾期</option>
        </select>
        {% if current_user.role in ['leader', 'admin'] and plan.status != 'archived' %}
        <button class="cmp-toolbar-btn cmp-toolbar-btn--primary" data-bs-toggle="modal" data-bs-target="#addValveModal"><i class="bi bi-plus-lg"></i> 添加阀门</button>
        {% endif %}
      </div>
    </div>
    <div class="table-responsive">
      <table class="cmp-table" id="itemTable">
        <thead>
          <tr>
            <th class="cmp-table__th">位号</th>
            <th class="cmp-table__th">设备名称</th>
            <th class="cmp-table__th">计划开始</th>
            <th class="cmp-table__th">计划截止</th>
            <th class="cmp-table__th">状态</th>
            <th class="cmp-table__th">关联维护</th>
            {% if current_user.role in ['leader', 'admin'] and plan.status != 'archived' %}
            <th class="cmp-table__th" style="width: 60px;">操作</th>
            {% endif %}
          </tr>
        </thead>
        <tbody>
          {% for item in items %}
          <tr class="item-row" data-status="{{ 'overdue' if item._overdue else item.status }}">
            <td class="cmp-table__td"><span class="cmp-table__td-link">{{ item.tag }}</span></td>
            <td class="cmp-table__td">{{ item.device_name or '-' }}</td>
            <td class="cmp-table__td">{{ item.planned_date_start }}</td>
            <td class="cmp-table__td">{{ item.planned_date_end }}</td>
            <td class="cmp-table__td">
              {% if item._overdue %}
              <span class="cmp-badge cmp-badge--pending" style="font-size: 12px;"><i class="bi bi-exclamation-triangle-fill"></i> 已逾期</span>
              {% elif item.status == 'completed' %}
              <span class="cmp-badge cmp-badge--approved" style="font-size: 12px;"><i class="bi bi-check-circle-fill"></i> 已完成</span>
              {% else %}
              <span class="cmp-badge" style="background: #f1f5f9; color: #475569; font-size: 12px;"><i class="bi bi-hourglass"></i> 待办</span>
              {% endif %}
            </td>
            <td class="cmp-table__td">
              {% if item.maintenance_record %}
              <a href="{{ url_for('valves.maintenance_edit', id=item.maintenance_id) }}" style="font-size: 13px; color: var(--mode-color);">{{ item.maintenance_record.检修时间.strftime('%Y-%m-%d') if item.maintenance_record.检修时间 else '' }} 检修</a>
              {% else %}<span style="color: var(--color-text-muted); font-size: 13px;">—</span>{% endif %}
            </td>
            {% if current_user.role in ['leader', 'admin'] and plan.status != 'archived' %}
            <td class="cmp-table__td">
              {% if item.status != 'completed' %}
              <form method="POST" action="{{ url_for('plans.remove_item', plan_id=plan.id, item_id=item.id) }}" style="display:inline;" onsubmit="return confirm('确认移除此项？')">
                <button class="cmp-toolbar-btn cmp-toolbar-btn--sm cmp-toolbar-btn--secondary" style="padding: 4px 8px;" title="移除"><i class="bi bi-x-lg"></i></button>
              </form>
              {% endif %}
            </td>
            {% endif %}
          </tr>
          {% else %}
          <tr><td colspan="7"><div class="cmp-empty"><i class="bi bi-inbox"></i><p>尚未添加阀门，请点击「添加阀门」按钮</p></div></td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {# 分页 #}
  </div>

  <!-- 添加阀门弹窗 -->
  {% if current_user.role in ['leader', 'admin'] and plan.status != 'archived' %}
  <div class="modal fade" id="addValveModal" tabindex="-1">
    <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
      <div class="modal-content" style="border-radius: 12px; border: none; box-shadow: 0 20px 60px rgba(0,0,0,0.2);">
        <div class="modal-header" style="border-bottom: 1px solid #f1f5f9; padding: 20px 24px;">
          <h5 class="modal-title" style="font-size: 18px; font-weight: 600;"><i class="bi bi-plus-circle me-2" style="color: var(--mode-color);"></i>从账户中选择阀门</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body" style="padding: 20px 24px;">
          <div class="row g-2 mb-3">
            <div class="col-md-5">
              <div class="input-group">
                <span class="input-group-text" style="background: #f8fafc; border-right: none;"><i class="bi bi-search text-muted"></i></span>
                <input type="text" id="deviceSearchInModal" class="form-control" placeholder="搜索位号..." style="border-left: none;">
              </div>
            </div>
            <div class="col-md-3">
              <select id="deviceUnitFilter" class="cmp-select" style="height: 38px;">
                <option value="">全部装置</option>
                {% for unit in approved_devices|map(attribute='unit')|unique|sort %}
                {% if unit %}<option value="{{ unit }}">{{ unit }}</option>{% endif %}
                {% endfor %}
              </select>
            </div>
            <div class="col-md-2">
              <span class="text-muted" style="line-height: 38px; font-size: 14px;">已选 <strong id="selectedCount">0</strong> 项</span>
            </div>
          </div>
          <div style="max-height: 300px; overflow-y: auto; border: 1px solid var(--color-border); border-radius: var(--radius-sm);">
            <table class="cmp-table" style="margin: 0;">
              <thead>
                <tr>
                  <th style="width: 40px;" class="cmp-table__th"><input type="checkbox" class="form-check-input" id="selectAllModal"></th>
                  <th class="cmp-table__th">位号</th>
                  <th class="cmp-table__th">设备名称</th>
                  <th class="cmp-table__th">装置名称</th>
                  <th class="cmp-table__th">类型</th>
                </tr>
              </thead>
              <tbody id="deviceTableBody">
                {% for dev in approved_devices %}
                <tr class="device-row" data-tag="{{ dev.tag }}" data-name="{{ dev.name }}" data-unit="{{ dev.unit }}" data-type="{{ dev.type }}" data-id="{{ dev.id }}">
                  <td class="cmp-table__td"><input type="checkbox" class="form-check-input device-checkbox"></td>
                  <td class="cmp-table__td" style="font-weight: 500; color: var(--color-primary);">{{ dev.tag }}</td>
                  <td class="cmp-table__td">{{ dev.name }}</td>
                  <td class="cmp-table__td">{{ dev.unit }}</td>
                  <td class="cmp-table__td">{{ dev.type }}</td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
          <div class="mt-3" style="border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 12px 16px; background: #fafbfc;">
            <div style="font-size: 13px; font-weight: 600; margin-bottom: 8px;"><i class="bi bi-calendar-range"></i> 批量设置计划日期</div>
            <div class="row g-2">
              <div class="col-md-4">
                <label style="font-size: 12px; color: var(--color-text-muted);">计划开始日期</label>
                <input type="date" id="batchDateStart" class="form-control form-control-sm">
              </div>
              <div class="col-md-4">
                <label style="font-size: 12px; color: var(--color-text-muted);">计划截止日期</label>
                <input type="date" id="batchDateEnd" class="form-control form-control-sm">
              </div>
              <div class="col-md-4 d-flex align-items-end">
                <button class="cmp-toolbar-btn cmp-toolbar-btn--primary btn-sm" onclick="applyBatchDates()"><i class="bi bi-arrow-right"></i> 应用到已选项</button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer" style="border-top: 1px solid #f1f5f9; padding: 16px 24px;">
          <button type="button" class="btn btn-light" data-bs-dismiss="modal" style="background: #f1f5f9; border: none; color: #475569; padding: 10px 20px; border-radius: 8px;">取消</button>
          <button type="button" class="btn cmp-btn cmp-btn--primary" id="confirmAddDevices" style="padding: 10px 20px; border-radius: 8px;"><i class="bi bi-check-lg"></i> 确认添加</button>
        </div>
      </div>
    </div>
  </div>
  {% endif %}
</div>
{% endblock %}

{% block extra_js %}
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
{% if plan.status == 'published' %}
// 环形进度
var c = document.getElementById('progressChart');
if (c) {
  var ctx = c.getContext('2d');
  var x = 70, y = 70, r = 58, sw = 10;
  ctx.clearRect(0, 0, 140, 140);
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.strokeStyle = '#e2e8f0';
  ctx.lineWidth = sw;
  ctx.stroke();
  var pct = {{ pct / 100 }};
  ctx.beginPath();
  ctx.arc(x, y, r, -Math.PI / 2, -Math.PI / 2 + Math.min(pct, 1) * Math.PI * 2);
  ctx.strokeStyle = '#10b981';
  ctx.lineWidth = sw;
  ctx.lineCap = 'round';
  ctx.stroke();
}
{% endif %}

// 搜索筛选逻辑
var approvedDevices = {{ approved_devices|tojson }};

document.getElementById('deviceSearchInModal')?.addEventListener('input', filterDevices);
document.getElementById('deviceUnitFilter')?.addEventListener('change', filterDevices);

function filterDevices() {
  var keyword = (document.getElementById('deviceSearchInModal').value || '').toLowerCase();
  var unit = document.getElementById('deviceUnitFilter').value;
  var rows = document.querySelectorAll('#deviceTableBody .device-row');
  rows.forEach(function(row) {
    var tag = (row.dataset.tag || '').toLowerCase();
    var name = (row.dataset.name || '').toLowerCase();
    var rowUnit = row.dataset.unit || '';
    var match = (!keyword || tag.includes(keyword) || name.includes(keyword)) && (!unit || rowUnit === unit);
    row.style.display = match ? '' : 'none';
  });
}

// 全选
document.getElementById('selectAllModal')?.addEventListener('change', function() {
  document.querySelectorAll('.device-row:not([style*=\"display: none\"]) .device-checkbox').forEach(function(cb) {
    cb.checked = this.checked;
  }.bind(this));
  updateSelectedCount();
});

// 更新已选计数
function updateSelectedCount() {
  var count = document.querySelectorAll('.device-checkbox:checked').length;
  document.getElementById('selectedCount').textContent = count;
}
document.querySelectorAll('.device-checkbox').forEach(function(cb) {
  cb.addEventListener('change', updateSelectedCount);
});

// 批量设置日期
function applyBatchDates() {
  var start = document.getElementById('batchDateStart').value;
  var end = document.getElementById('batchDateEnd').value;
  // Store in data attributes for later use
  document.querySelectorAll('.device-checkbox:checked').forEach(function(cb) {
    cb.dataset.start = start;
    cb.dataset.end = end;
  });
}

// 确认添加
document.getElementById('confirmAddDevices')?.addEventListener('click', function() {
  var checked = document.querySelectorAll('.device-checkbox:checked');
  if (checked.length === 0) { alert('请至少选择一项'); return; }

  var devices = [];
  var defaultStart = document.getElementById('batchDateStart').value;
  var defaultEnd = document.getElementById('batchDateEnd').value;

  // 获取设备数据
  checked.forEach(function(cb) {
    var row = cb.closest('.device-row');
    devices.push({
      id: row.dataset.id,
      type: row.dataset.type,
      tag: row.dataset.tag,
      name: row.dataset.name,
      start: cb.dataset.start || defaultStart,
      end: cb.dataset.end || defaultEnd,
    });
  });

  fetch('{{ url_for("plans.add_items", id=plan.id) }}', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      devices: devices.map(function(d) { return {id: d.id, type: d.type, tag: d.tag, name: d.name}; }),
      planned_date_start: defaultStart,
      planned_date_end: defaultEnd,
    }),
  }).then(function(r) { return r.json(); }).then(function(data) {
    location.reload();
  });
});
</script>
{% endblock %}
```

- [ ] **Step 4: Verify templates render**

```bash
cd /home/mrg/work/InstrumentValveLedgerSystem
uv run python -c "
from app import create_app
app = create_app()
with app.app_context():
    from flask import render_template
    rendered = render_template('plans/list.html', plans=[], stats={})
    print(f'list.html rendered: {len(rendered)} chars')
    rendered = render_template('plans/form.html')
    print(f'form.html rendered: {len(rendered)} chars')
"
```

- [ ] **Step 5: Commit**

```bash
git add templates/plans/
git commit -m "feat: add plan list, form, detail templates"
```

---

### Task 5: Maintenance Record Integration

**Files:**
- Modify: `app/routes/valves/attachments.py` — `maintenance_create()` and `maintenance_edit()`
- Modify: `templates/maintenance/create.html` — 添加计划关联下拉框
- Modify: `templates/maintenance/edit.html` — 显示关联计划信息
- Modify: `templates/maintenance/list.html` — 新增「所属计划」列

- [ ] **Step 1: Add helper to get pending plan items for a device**

在 `maintenance_create` 中添加获取 pending plan items 的逻辑：

```python
# In maintenance_create(), after valves_data:
pending_plan_items = []
if current_user.role in ("employee", "admin") and valve:
    from app.models import MaintenancePlan, MaintenancePlanItem
    pending_plan_items = (
        db.session.query(MaintenancePlanItem, MaintenancePlan.title)
        .join(MaintenancePlan, MaintenancePlan.id == MaintenancePlanItem.plan_id)
        .filter(
            MaintenancePlanItem.device_type == valve_type,  # Need to handle after selection
            MaintenancePlanItem.status == "pending",
            MaintenancePlan.status == "published",
        )
        .all()
    )
```

但更好的方式是在选择阀门后动态加载。让前端在选择阀门后通过 AJAX 请求获取可关联的计划项。

实际上，更简单的方式：在 `maintenance_create()` 中，POST 时如果收到 `plan_item_id`，则更新计划项状态。GET 时传递所有可用的计划项数据给模板，模板根据选中的阀门动态显示。

最佳方式是：用户选择阀门后，通过 AJAX 获取该阀门的可用计划项列表。但为了减少复杂度，最简单的做法是：

在 `maintenance_create()` 的 GET 处理中，查询所有已发布计划中、状态为 pending 的 MaintenancePlanItem，按 device_type+device_id 分组，传递给模板。模板根据用户选择的阀门过滤。

实现：

```python
# 在 maintenance_create() 中，GET 请求时追加 plan_items_data
plan_items_query = db.session.query(
    MaintenancePlanItem, MaintenancePlan.title
).join(
    MaintenancePlan, MaintenancePlan.id == MaintenancePlanItem.plan_id
).filter(
    MaintenancePlanItem.status == "pending",
    MaintenancePlan.status == "published",
)
plan_items_data = {
    f"{item.MaintenancePlanItem.device_type}:{item.MaintenancePlanItem.device_id}": {
        "item_id": item.MaintenancePlanItem.id,
        "plan_title": item.title,
        "tag": item.MaintenancePlanItem.tag,
        "planned_date_end": item.MaintenancePlanItem.planned_date_end.isoformat() if item.MaintenancePlanItem.planned_date_end else "",
    }
    for item in plan_items_query.all()
}

return render_template(
    "maintenance/create.html",
    valves=valves,
    valves_data=valves_data,
    plan_items_data=plan_items_data,
)
```

- [ ] **Step 2: Handle `plan_item_id` in POST**

在 `maintenance_create()` POST 保存逻辑后，追加 plan_item 关联代码：

```python
# After db.session.commit() for the maintenance record
plan_item_id = request.form.get("plan_item_id")
if plan_item_id:
    try:
        plan_item_id = int(plan_item_id)
        plan_item = MaintenancePlanItem.query.get(plan_item_id)
        if plan_item and plan_item.status == "pending":
            plan_item.status = "completed"
            plan_item.maintenance_id = record.id
            plan_item.completed_at = datetime.utcnow()
            plan_item.completed_by = current_user.id
            # Update plan progress
            plan = MaintenancePlan.query.get(plan_item.plan_id)
            if plan:
                plan.completed_items = MaintenancePlanItem.query.filter_by(
                    plan_id=plan.id, status="completed"
                ).count()
            flash("已关联检修计划并更新进度")
    except (ValueError, TypeError):
        pass
```

在 `maintenance_edit()` 中也做类似处理（当用户修改 valve_id/valve_type 时可能需要清除旧关联）。

- [ ] **Step 3: Update `templates/maintenance/create.html`**

在表单底部（检修内容后面）追加：

```html
<div class="mb-3" style="border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 16px; background: #fafbfc;">
  <label class="cmp-label" style="margin-bottom: 8px;"><i class="bi bi-link-45deg" style="color: var(--mode-color);"></i> 关联检修计划</label>
  <div style="display: flex; align-items: center; gap: 12px;">
    <select name="plan_item_id" id="planItemSelect" class="cmp-select" style="width: auto; min-width: 280px; height: 38px;" disabled>
      <option value="">不关联计划（普通维护）</option>
    </select>
    <span style="font-size: 12px; color: var(--color-text-muted);">
      <i class="bi bi-check-circle-fill" style="color: #10b981;"></i> 关联后自动推进计划进度
    </span>
  </div>
  <div id="planItemInfo" style="display:none; margin-top: 8px; font-size: 13px; color: var(--color-text-muted);"></div>
</div>

<script>
// plan_items_data is a dict keyed by "device_type:device_id"
var planItemsData = {{ plan_items_data|tojson }};

// When valve is selected, populate the plan item dropdown
document.getElementById('valveSelectConfirm').addEventListener('click', function() {
  // existing code...
  updatePlanItems(selectedValveType, selectedValveId);
});

function updatePlanItems(deviceType, deviceId) {
  var select = document.getElementById('planItemSelect');
  var info = document.getElementById('planItemInfo');
  select.innerHTML = '<option value="">不关联计划（普通维护）</option>';
  select.disabled = true;
  info.style.display = 'none';

  if (deviceType && deviceId) {
    var key = deviceType + ':' + deviceId;
    var items = planItemsData[key];
    if (items && items.length > 0) {
      items.forEach(function(item) {
        var opt = document.createElement('option');
        opt.value = item.item_id;
        opt.textContent = '[' + item.plan_title + '] ' + item.tag + '（截止：' + item.planned_date_end + '）';
        select.appendChild(opt);
      });
      select.disabled = false;
    } else {
      info.style.display = 'block';
      info.textContent = '该阀门暂无待执行计划项';
    }
  }
}
</script>
```

- [ ] **Step 4: Update `templates/maintenance/list.html`**

在表头 `<th>类型</th>` 后面追加 `<th class="cmp-table__th">所属计划</th>`，并在对应数据行追加：

```html
<td class="cmp-table__td">
  {% if record.plan_item %}
  <a href="{{ url_for('plans.detail', id=record.plan_item.plan_id) }}" style="font-size: 13px; color: var(--mode-color);">{{ record.plan_item.plan.title }}</a>
  {% else %}
  <span style="color: var(--color-text-muted); font-size: 13px;">—</span>
  {% endif %}
</td>
```

需要在 `MaintenanceRecord` 模型中添加 `plan_item` relationship，或通过查询获得。

简化方式：在 `maintenance_list()` 查询中，对每条记录查询关联的 MaintenancePlanItem。更好的方式是在 MaintenanceRecord 模型上加一个 `plan_item` 关系属性。但由于 maintenance_records 表里没有外键指向 MaintenancePlanItem（而是反过来），需要通过 `maintenance_id` 反向查找。

在 `maintenance_list()` 视图中：

```python
# 查询后，遍历记录设置 plan_item
for record in records:
    record._plan_item = MaintenancePlanItem.query.filter_by(
        maintenance_id=record.id
    ).first()
```

模板中使用 `record._plan_item`。

- [ ] **Step 5: Commit**

```bash
git add app/routes/valves/attachments.py templates/maintenance/
git commit -m "feat: integrate maintenance records with plan items"
```

---

### Task 6: Employee Early Warning

**Files:**
- Modify: `app/routes/plans.py` — 追加 `early_warning` 路由
- Create: `templates/plans/early_warning.html`

- [ ] **Step 1: Implement `early_warning` route**

```python
@plans_bp.route("/plans/early-warning")
@login_required
def early_warning():
    if current_user.role not in ("employee", "admin"):
        flash("仅员工和管理员可查看预警")
        return redirect(url_for("plans.index"))

    now = date.today()
    from datetime import timedelta

    published_plan_ids = [p.id for p in MaintenancePlan.query.filter_by(status="published").all()]

    warning_items = (
        MaintenancePlanItem.query
        .filter(
            MaintenancePlanItem.plan_id.in_(published_plan_ids),
            MaintenancePlanItem.status == "pending",
            MaintenancePlanItem.planned_date_end <= (now + timedelta(days=7)).isoformat(),
        )
        .order_by(MaintenancePlanItem.planned_date_end.asc())
        .all()
    )

    overdue = []
    upcoming = []
    for item in warning_items:
        plan = MaintenancePlan.query.get(item.plan_id)
        if not plan:
            continue
        item._plan_title = plan.title
        item._days_left = (item.planned_date_end - now).days
        if item.planned_date_end < now:
            item._overdue_days = abs(item._days_left) if item._days_left < 0 else 0
            overdue.append(item)
        else:
            upcoming.append(item)

    # 统计
    stats = {
        "overdue": len(overdue),
        "upcoming_7days": len(upcoming),
        "monthly": MaintenancePlanItem.query.filter(
            MaintenancePlanItem.plan_id.in_(published_plan_ids),
            MaintenancePlanItem.status == "pending",
            MaintenancePlanItem.planned_date_end <= date(now.year, now.month + 1, 1) - timedelta(days=1) if now.month < 12 else date(now.year + 1, 1, 1) - timedelta(days=1),
            MaintenancePlanItem.planned_date_end >= now.isoformat(),
        ).count(),
    }

    return render_template(
        "plans/early_warning.html",
        overdue=overdue,
        upcoming=upcoming,
        stats=stats,
    )
```

- [ ] **Step 2: Create `templates/plans/early_warning.html`**

参考 `design-prototypes/plans-employee-early-warning.html`，使用 `cmp-stat` 统计卡片 + 预警项列表，每项显示位号、设备名称、计划日期、所属计划、逾期天数/剩余天数，末尾附「创建维护记录」按钮。

核心模板逻辑：

```html
{% extends "base.html" %}
{% block page_title %}检修预警{% endblock %}
{% block content %}
<!-- 统计卡片 -->
<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px;">
  <div class="cmp-stat danger">
    <div class="stat-icon danger"><i class="bi bi-exclamation-triangle-fill"></i></div>
    <div class="stat-content"><h3>已逾期</h3><p><span class="stat-value" style="color: #dc2626;">{{ stats.overdue }}</span> 项</p></div>
  </div>
  <div class="cmp-stat warning">
    <div class="stat-icon warning"><i class="bi bi-clock-fill"></i></div>
    <div class="stat-content"><h3>7天内到期</h3><p><span class="stat-value" style="color: #d97706;">{{ stats.upcoming_7days }}</span> 项</p></div>
  </div>
  <div class="cmp-stat info">
    <div class="stat-icon info"><i class="bi bi-calendar-week"></i></div>
    <div class="stat-content"><h3>本月待办</h3><p><span class="stat-value" style="color: #2563eb;">{{ stats.monthly }}</span> 项</p></div>
  </div>
</div>

<!-- 筛选 -->
<div class="cmp-toolbar cmp-toolbar--card" style="margin-bottom: 16px;">
  <div class="cmp-toolbar__left">
    <select id="warningFilter" class="cmp-toolbar-filter cmp-select" style="width: auto; min-width: 130px;">
      <option value="all">全部状态</option>
      <option value="overdue">已逾期</option>
      <option value="upcoming">即将到期</option>
    </select>
    <div class="cmp-toolbar-search">
      <i class="bi bi-search"></i>
      <input type="text" id="warningSearch" placeholder="搜索位号..." style="padding-left: 32px; height: 36px; width: 180px; font-size: 13px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--gray-50);">
    </div>
  </div>
</div>

<!-- 逾期项 -->
{% for item in overdue %}
<div class="cmp-card" style="padding: 0; overflow: hidden; border-left: 4px solid #ef4444; margin-bottom: 12px;">
  <div style="display: flex; align-items: center; padding: 16px 20px; gap: 16px;">
    <div style="width: 44px; height: 44px; border-radius: 10px; background: #fef2f2; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
      <i class="bi bi-exclamation-triangle-fill" style="font-size: 20px; color: #ef4444;"></i>
    </div>
    <div style="flex: 1;">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
        <span style="font-size: 16px; font-weight: 600;">{{ item.tag }}</span>
        <span style="font-size: 13px; color: var(--color-text-muted);">{{ item.device_name }}</span>
        <span class="cmp-badge" style="background: #fef2f2; color: #dc2626; border-color: #fecaca; font-size: 12px; padding: 2px 10px;">
          <i class="bi bi-exclamation-triangle-fill"></i> 已逾期 {{ item._overdue_days }} 天
        </span>
      </div>
      <div style="display: flex; gap: 20px; font-size: 13px; color: var(--color-text-muted);">
        <span><i class="bi bi-calendar-range"></i> {{ item.planned_date_start }} ~ {{ item.planned_date_end }}</span>
        <span><i class="bi bi-folder"></i> {{ item._plan_title }}</span>
      </div>
    </div>
    <div style="flex-shrink: 0;">
      <a href="{{ url_for('valves.maintenance_create', plan_item_id=item.id) }}" class="cmp-btn cmp-btn--primary cmp-btn--sm"><i class="bi bi-tools"></i> 创建维护记录</a>
    </div>
  </div>
</div>
{% endfor %}

<!-- 即将到期项 -->
{% for item in upcoming %}
<div class="cmp-card" style="padding: 0; overflow: hidden; border-left: 4px solid #f59e0b; margin-bottom: 12px;">
  <div style="display: flex; align-items: center; padding: 16px 20px; gap: 16px;">
    <div style="width: 44px; height: 44px; border-radius: 10px; background: #fffbeb; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
      <i class="bi bi-clock-fill" style="font-size: 20px; color: #f59e0b;"></i>
    </div>
    <div style="flex: 1;">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
        <span style="font-size: 16px; font-weight: 600;">{{ item.tag }}</span>
        <span style="font-size: 13px; color: var(--color-text-muted);">{{ item.device_name }}</span>
        <span class="cmp-badge" style="background: #fffbeb; color: #d97706; border-color: #fde68a; font-size: 12px; padding: 2px 10px;">
          <i class="bi bi-clock"></i> 还剩 {{ item._days_left }} 天
        </span>
      </div>
      <div style="display: flex; gap: 20px; font-size: 13px; color: var(--color-text-muted);">
        <span><i class="bi bi-calendar-range"></i> {{ item.planned_date_start }} ~ {{ item.planned_date_end }}</span>
        <span><i class="bi bi-folder"></i> {{ item._plan_title }}</span>
      </div>
    </div>
    <div style="flex-shrink: 0;">
      <a href="{{ url_for('valves.maintenance_create', plan_item_id=item.id) }}" class="cmp-btn cmp-btn--primary cmp-btn--sm"><i class="bi bi-tools"></i> 创建维护记录</a>
    </div>
  </div>
</div>
{% endfor %}

{% if not overdue and not upcoming %}
<div class="cmp-empty"><i class="bi bi-check-circle-fill" style="color: #10b981;"></i><p>没有即将到期或逾期的检修项</p></div>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add app/routes/plans.py templates/plans/early_warning.html
git commit -m "feat: add employee early warning page"
```

---

### Task 7: Navigation + Homepage + Notifications + Context Processor

**Files:**
- Modify: `templates/base.html` — 侧边栏增加「检修计划」和「检修预警」入口
- Modify: `templates/index_employee.html` — 增加预警卡片
- Modify: `templates/index_leader.html` — 增加计划统计卡片
- Modify: `templates/index_admin.html` — 增加计划统计卡片
- Modify: `app/routes/plans.py` — 追加 notification 路由
- Modify: `app/__init__.py` — 注册通知相关的上下文处理器

- [ ] **Step 1: Update `templates/base.html` 侧边栏**

在 sidebar-menu 中合适位置插入：

对于所有用户（在「审批中心」之前或「全部台账」之后）：

```html
<a href="{{ url_for('plans.index') }}" class="sidebar-menu-item">
  <i class="bi bi-calendar-check"></i><span>检修计划</span>
</a>
```

对于员工和管理员，追加预警入口（带徽标）：

```html
{% if current_user.role in ['employee', 'admin'] %}
<a href="{{ url_for('plans.early_warning') }}" class="sidebar-menu-item">
  <i class="bi bi-exclamation-triangle"></i><span>检修预警</span>
  {% if plan_warning_count > 0 %}
  <span class="badge bg-danger ms-auto">{{ plan_warning_count }}</span>
  {% endif %}
</a>
{% endif %}
```

- [ ] **Step 2: Update homepage 统计卡片**

`templates/index_employee.html` 追加（在维护记录卡片后面）：

```html
<a href="{{ url_for('plans.early_warning') }}" class="cmp-stat danger">
  <div class="stat-icon danger"><i class="bi bi-exclamation-triangle-fill"></i></div>
  <div class="stat-content">
    <h3>检修预警</h3>
    <p><span class="stat-value">{{ plan_warning_count }}</span> 项待处理</p>
  </div>
</a>
```

`templates/index_leader.html` 追加：

```html
<a href="{{ url_for('plans.index') }}" class="cmp-stat primary">
  <div class="stat-icon primary"><i class="bi bi-calendar-check"></i></div>
  <div class="stat-content">
    <h3>检修计划</h3>
    <p><span class="stat-value">{{ plan_stats.published }}</span> 个已发布 · 共 {{ plan_stats.total }} 个</p>
  </div>
</a>
```

在 `app/__init__.py` 的 `inject_pending_count` 上下文处理器中追加 `plan_warning_count` 和 `plan_stats`。

- [ ] **Step 3: Implement notification routes**

在 `app/routes/plans.py` 追加：

```python
@plans_bp.route("/notifications")
@login_required
def notification_list():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).all()
    return render_template("plans/notifications.html", notifications=notifications)


@plans_bp.route("/notifications/<int:id>/read", methods=["POST"])
@login_required
def mark_notification_read(id):
    notification = Notification.query.get_or_404(id)
    if notification.user_id != current_user.id:
        abort(403)
    notification.is_read = True
    db.session.commit()
    return redirect(url_for("plans.notification_list"))


@plans_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def read_all_notifications():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("已全部标记为已读")
    return redirect(url_for("plans.notification_list"))


@plans_bp.route("/notifications/unread-count")
@login_required
def unread_notification_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return {"count": count}
```

- [ ] **Step 4: Create `templates/plans/notifications.html`**

```html
{% extends "base.html" %}
{% block page_title %}通知消息{% endblock %}
{% block content %}
<div class="cmp-card" style="padding: 0; overflow: hidden;">
  <div style="padding: 16px 24px; border-bottom: 1px solid var(--color-border); display: flex; justify-content: space-between; align-items: center;">
    <h5 style="margin: 0; font-size: 16px; font-weight: 600;">通知消息</h5>
    {% if notifications|selectattr('is_read', 'equalto', false)|list|length > 0 %}
    <form method="POST" action="{{ url_for('plans.read_all_notifications') }}" style="display:inline;">
      <button class="cmp-toolbar-btn cmp-toolbar-btn--secondary"><i class="bi bi-check2-all"></i> 全部已读</button>
    </form>
    {% endif %}
  </div>
  <div>
    {% for notif in notifications %}
    <div style="padding: 16px 24px; border-bottom: 1px solid var(--color-border); {% if not notif.is_read %}background: #f0fdf4;{% endif %}">
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div>
          <div style="display: flex; align-items: center; gap: 8px;">
            {% if not notif.is_read %}<span style="width: 8px; height: 8px; border-radius: 50%; background: #10b981; display: inline-block;"></span>{% endif %}
            <strong style="font-size: 15px;">{{ notif.title }}</strong>
          </div>
          {% if notif.content %}<p style="margin: 4px 0 0 16px; font-size: 14px; color: var(--color-text-muted);">{{ notif.content }}</p>{% endif %}
        </div>
        <div style="text-align: right; flex-shrink: 0;">
          <div style="font-size: 12px; color: var(--color-text-muted);">{{ notif.created_at.strftime('%Y-%m-%d %H:%M') }}</div>
          {% if not notif.is_read %}
          <form method="POST" action="{{ url_for('plans.mark_notification_read', id=notif.id) }}" style="display:inline; margin-top: 4px;">
            <button class="btn btn-sm btn-link" style="text-decoration: none; padding: 0; font-size: 12px;">标记已读</button>
          </form>
          {% endif %}
        </div>
      </div>
      {% if notif.ref_type == 'plan' %}
      <div style="margin-top: 8px;">
        <a href="{{ url_for('plans.detail', id=notif.ref_id) }}" class="cmp-toolbar-btn cmp-toolbar-btn--primary btn-sm"><i class="bi bi-eye"></i> 查看计划</a>
      </div>
      {% endif %}
    </div>
    {% else %}
    <div class="cmp-empty"><i class="bi bi-bell"></i><p>暂无通知</p></div>
    {% endfor %}
  </div>
</div>
{% endblock %}
```

在实际导航栏中，铃铛入口可以这样在 `base.html` 添加：

在 `header-actions` 区域增加通知铃铛：

```html
{% if current_user.is_authenticated %}
<div class="dropdown" style="position: relative;">
  <button class="btn btn-sm position-relative" data-bs-toggle="dropdown" style="background: transparent; border: none; font-size: 20px; color: var(--color-text-muted);">
    <i class="bi bi-bell"></i>
    {% if unread_count > 0 %}
    <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger" style="font-size: 10px; min-width: 18px;">
      {{ unread_count }}
    </span>
    {% endif %}
  </button>
  <div class="dropdown-menu dropdown-menu-end" style="min-width: 320px; padding: 0; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.12); border: none;">
    <div style="padding: 12px 16px; border-bottom: 1px solid var(--color-border);">
      <strong>通知</strong>
      <form method="POST" action="{{ url_for('plans.read_all_notifications') }}" style="display:inline; float: right;">
        <button class="btn btn-sm btn-link" style="text-decoration: none; padding: 0;">全部已读</button>
      </form>
    </div>
    <div style="max-height: 300px; overflow-y: auto;">
      {% for notif in recent_notifications %}
      <a href="{{ url_for('plans.detail', id=notif.ref_id) if notif.ref_type == 'plan' else '#' }}" class="dropdown-item" style="padding: 12px 16px; border-bottom: 1px solid #f1f5f9; {% if not notif.is_read %}background: #f0fdf4;{% endif %}">
        <div style="font-size: 14px; font-weight: 500;">{{ notif.title }}</div>
        <div style="font-size: 12px; color: var(--color-text-muted);">{{ notif.created_at.strftime('%m-%d %H:%M') }}</div>
      </a>
      {% else %}
      <div style="padding: 24px; text-align: center; color: var(--color-text-muted); font-size: 14px;">暂无通知</div>
      {% endfor %}
    </div>
  </div>
</div>
{% endif %}
```

- [ ] **Step 5: 在 `app/__init__.py` 的 context_processor 中注入通知数据**

在 `inject_pending_count` 中追加：

```python
if current_user.is_authenticated:
    # Notifications
    unread_count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    recent_notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(5).all()
else:
    unread_count = 0
    recent_notifications = []

# Plan stats
plan_stats = {
    "total": MaintenancePlan.query.count(),
    "published": MaintenancePlan.query.filter_by(status="published").count(),
    "draft": MaintenancePlan.query.filter_by(status="draft").count(),
}

return dict(
    pending_count=pending_count,
    VALVE_TYPES=VALVE_TYPES,
    unread_count=unread_count,
    recent_notifications=recent_notifications,
    plan_stats=plan_stats,
)
```

- [ ] **Step 6: Test homepage 加载正常**

```bash
cd /home/mrg/work/InstrumentValveLedgerSystem
uv run python -c "
from app import create_app
app = create_app()
with app.test_client() as client:
    # Login
    resp = client.post('/login', data={'username': 'ld001', 'password': 'ld001'}, follow_redirects=True)
    print(f'Leader home: {resp.status_code}')
    resp = client.post('/login', data={'username': '化工班', 'password': '111'}, follow_redirects=True)
    print(f'Employee home: {resp.status_code}')
"
```

- [ ] **Step 7: Commit**

```bash
git add templates/base.html templates/index_*.html app/routes/plans.py app/__init__.py
git commit -m "feat: add navigation, notifications, and homepage integration for plans"
```

---

### Task 8: Integration Tests

**Files:**
- Create: `tests/test_plans.py`

- [ ] **Step 1: Write basic plan CRUD test**

```python
import pytest
from flask import url_for


class TestPlans:
    def test_leader_can_create_plan(self, client, login_leader):
        resp = client.post("/plan/new", data={"title": "测试计划", "description": "测试描述"}, follow_redirects=True)
        assert resp.status_code == 200
        assert b"测试计划" in resp.data or b"保存" in resp.data

    def test_employee_cannot_create_plan(self, client, login_employee):
        resp = client.post("/plan/new", data={"title": "测试计划"}, follow_redirects=True)
        assert resp.status_code == 200
        assert b"无权创建" in resp.data

    def test_plan_list_shows_correctly(self, client, login_leader):
        resp = client.get("/plans")
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests**

```bash
cd /home/mrg/work/InstrumentValveLedgerSystem
uv run pytest tests/test_plans.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_plans.py
git commit -m "test: add basic plan CRUD tests"
```

---

### 验证清单

功能验收测试要点：

- [ ] 领导可新建计划（草稿）
- [ ] 领导可在草稿计划中添加/移除阀门
- [ ] 领导可发布计划，员工收到通知
- [ ] 员工可在预警页面看到即将到期/逾期项
- [ ] 员工可从预警页面创建维护记录，自动关联计划项
- [ ] 维护记录关联后，计划进度更新
- [ ] 领导可在计划详情页查看进度看板
- [ ] 员工无法创建/编辑/删除计划
- [ ] 已归档计划不可修改
