# 台账列表界面优化实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 优化阀门台账列表界面，实现表头冻结功能

**Architecture:** 修改 templates/valves/list.html 的 CSS 样式，使用 position: sticky 实现表头冻结

**Tech Stack:** HTML, CSS (内联样式)

---

### Task 1: 修改表格容器样式

**Files:**
- Modify: `templates/valves/list.html:98-99`

**Step 1: 添加 position: relative 到表格容器**

```html
<!-- 原代码 -->
<div class="modern-card">
    <div class="table-responsive" style="height: calc(100vh - 180px); overflow-y: auto; overflow-x: auto;">

<!-- 修改为 -->
<div class="modern-card">
    <div class="table-responsive" style="height: calc(100vh - 180px); overflow-y: auto; overflow-x: auto; position: relative;">
```

---

### Task 2: 修改表头分组行样式（第一行）

**Files:**
- Modify: `templates/valves/list.html:101-112`

**Step 1: 为表头分组行添加 sticky 样式**

```html
<!-- 原代码 -->
<thead class="table-light">
    <tr>
        <th style="width: 50px; min-width: 50px; vertical-align: middle; position: sticky; left: 0; z-index: 3; background: #f8f9fa; border-right: 1px solid #dee2e6;">
        <th colspan="11" class="text-center table-secondary">基础信息</th>
        <th colspan="4" class="text-center table-info">工艺条件</th>
        <th colspan="3" class="text-center table-warning">阀体信息</th>
        <th colspan="7" class="text-center table-danger">阀内件信息</th>
        <th colspan="10" class="text-center table-success">执行机构信息</th>
        <th colspan="2" class="text-center" style="background: #f8f9fa;">操作列</th>
    </tr>

<!-- 修改为 -->
<thead class="table-light" style="position: sticky; top: 0; z-index: 20;">
    <tr>
        <th style="width: 50px; min-width: 50px; vertical-align: middle; position: sticky; left: 0; z-index: 23; background: #f8f9fa; border-right: 1px solid #dee2e6;">
        <th colspan="11" class="text-center table-secondary" style="position: sticky; left: 50px; z-index: 21;">基础信息</th>
        <th colspan="4" class="text-center table-info" style="position: sticky; z-index: 21;">工艺条件</th>
        <th colspan="3" class="text-center table-warning" style="position: sticky; z-index: 21;">阀体信息</th>
        <th colspan="7" class="text-center table-danger" style="position: sticky; z-index: 21;">阀内件信息</th>
        <th colspan="10" class="text-center table-success" style="position: sticky; z-index: 21;">执行机构信息</th>
        <th colspan="2" class="text-center" style="position: sticky; right: 0; z-index: 23; background: #f8f9fa;">操作列</th>
    </tr>
```

---

### Task 3: 修改表头字段行样式（第二行）

**Files:**
- Modify: `templates/valves/list.html:113-146`

**Step 1: 为表头字段行添加 sticky 样式**

```html
<!-- 原代码 -->
<tr>
    <th style="width: 50px; min-width: 50px; position: sticky; left: 0; z-index: 3; background: #f8f9fa; border-right: 1px solid #dee2e6;"></th>
    {% set fields = [...] %}
    {% for field, label, width, style in fields %}
    <th {% if style == 'sticky' %}style="min-width: {{ width }}px; position: sticky; right: {{ '100px' if field == '状态' else '0px' }}; z-index: 3; background: #f8f9fa;"{% else %}class="filter-header" data-field="{{ field }}" style="min-width: {{ width }}px; cursor: pointer;" onclick="showFilterDropdown(event, '{{ field }}')"{% endif %}>
        ...
    </th>
    {% endfor %}
</tr>

<!-- 修改为 -->
<tr>
    <th style="width: 50px; min-width: 50px; position: sticky; left: 0; z-index: 22; background: #f8f9fa; border-right: 1px solid #dee2e6; border-bottom: 2px solid #dee2e6;"></th>
    {% set fields = [...] %}
    {% for field, label, width, style in fields %}
    <th {% if style == 'sticky' %}style="min-width: {{ width }}px; position: sticky; right: {{ '100px' if field == '状态' else '0px' }}; z-index: 22; background: #f8f9fa; border-bottom: 2px solid #dee2e6;"{% else %}class="filter-header" data-field="{{ field }}" style="min-width: {{ width }}px; cursor: pointer; position: sticky; left: 50px; z-index: 21; border-bottom: 2px solid #dee2e6;" onclick="showFilterDropdown(event, '{{ field }}')"{% endif %}>
        ...
    </th>
    {% endfor %}
</tr>
```

---

### Task 4: 验证表头冻结效果

**Step 1: 启动开发服务器**

```bash
cd G:\work\python\InstrumentValveLedgerSystem
uv run flask run --debug
```

**Step 2: 访问页面验证**

在浏览器中打开 http://127.0.0.1:5000/valves/list 检查：
1. 垂直滚动时表头是否保持固定
2. 水平滚动时首尾列是否保持固定
3. 表头背景色是否正确显示
4. 现有功能（搜索、筛选、分页）是否正常

---

### Task 5: 提交代码

```bash
git add templates/valves/list.html docs/plans/2026-02-25-ledger-list-optimization-design.md
git commit -m "feat: 优化台账列表界面，实现表头冻结功能"
```
