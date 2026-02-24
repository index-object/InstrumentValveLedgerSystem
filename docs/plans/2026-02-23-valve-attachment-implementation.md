# 附件功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在新建/编辑台账界面第6步添加附件功能，支持添加多个附件（定位器、过滤减压阀、减压阀、电磁阀、接近开关等）

**Architecture:** 修改前端form.html模板第6步为附件区域，修改后端routes/valves.py的new和edit路由解析并保存附件数据

**Tech Stack:** Flask, Jinja2模板, Bootstrap 5, JavaScript

---

## 任务清单

### 任务1: 修改前端模板 - 将第6步改为附件区域

**文件:**
- Modify: `templates/valves/form.html:401-424`

**步骤1: 修改步骤名称**

将步骤6的标签从"备注信息"改为"附件信息"：

```html
<div class="step-item" data-step="6" onclick="goToStep(6)">
    <div class="step-number">6</div>
    <div class="step-label">附件信息</div>
</div>
```

**步骤2: 替换第6步内容**

将现有的备注信息区域替换为附件信息区域：

```html
<div class="form-step" data-step="6">
    <div class="form-section" id="attachments">
        <div class="form-section-header" style="background: linear-gradient(135deg, #6b7280 0%, #9ca3af 100%);">
            <i class="bi bi-paperclip"></i>
            <h5>附件信息</h5>
        </div>
        <div class="form-section-body">
            <div id="attachments-container">
                <!-- 附件行将通过JS动态添加 -->
            </div>
            <button type="button" class="btn btn-outline-primary mt-3" onclick="addAttachment()">
                <i class="bi bi-plus-circle"></i> 添加附件
            </button>
        </div>
    </div>
    <div class="step-actions">
        <button type="button" class="btn-back" onclick="goToStep(5)">
            <i class="bi bi-arrow-left"></i> 上一步
        </button>
        <div class="d-flex gap-3">
            <button type="submit" class="btn-submit">
                <i class="bi bi-check-circle"></i> 提交审批
            </button>
            <a href="{{ url_for('valves.list') }}" class="btn-back">
                <i class="bi bi-x-circle"></i> 取消
            </a>
        </div>
    </div>
</div>
```

**步骤3: 添加附件行的HTML模板**

在form结束标签前添加隐藏的附件行模板：

```html
<template id="attachment-row-template">
    <div class="attachment-row card mb-2">
        <div class="card-body py-2">
            <div class="field-row align-items-center">
                <div class="field-item" style="flex: 0 0 150px;">
                    <label class="form-label">附件类型</label>
                    <select name="attachment_type" class="form-control form-control-modern">
                        <option value="">请选择</option>
                        <option value="定位器">定位器</option>
                        <option value="过滤减压阀">过滤减压阀</option>
                        <option value="减压阀">减压阀</option>
                        <option value="电磁阀">电磁阀</option>
                        <option value="接近开关">接近开关</option>
                        <option value="其他">其他</option>
                    </select>
                </div>
                <div class="field-item">
                    <label class="form-label">名称</label>
                    <input type="text" name="attachment_name" class="form-control form-control-modern" placeholder="请输入名称">
                </div>
                <div class="field-item" style="flex: 0 0 100px;">
                    <label class="form-label">设备等级</label>
                    <input type="text" name="attachment_level" class="form-control form-control-modern" placeholder="如：A级">
                </div>
                <div class="field-item">
                    <label class="form-label">型号规格</label>
                    <input type="text" name="attachment_spec" class="form-control form-control-modern" placeholder="请输入型号规格">
                </div>
                <div class="field-item">
                    <label class="form-label">生产厂家</label>
                    <input type="text" name="attachment_manufacturer" class="form-control form-control-modern" placeholder="请输入生产厂家">
                </div>
                <div class="field-item" style="flex: 0 0 50px;">
                    <label class="form-label">&nbsp;</label>
                    <button type="button" class="btn btn-outline-danger btn-sm" onclick="removeAttachment(this)">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>
```

**步骤4: 添加JavaScript函数**

在script部分添加以下函数：

```javascript
function addAttachment() {
    const template = document.getElementById('attachment-row-template');
    const container = document.getElementById('attachments-container');
    const clone = template.content.cloneNode(true);
    container.appendChild(clone);
}

function removeAttachment(btn) {
    const row = btn.closest('.attachment-row');
    row.remove();
}

// 初始化时如果有已有附件，加载它们
document.addEventListener('DOMContentLoaded', function() {
    const existingAttachments = {{ valve.attachments|tojson if valve else '[]' }};
    existingAttachments.forEach(function(attachment) {
        addAttachmentWithData(attachment);
    });
    // 如果没有已有附件，默认添加一个空行
    if (existingAttachments.length === 0) {
        addAttachment();
    }
});

function addAttachmentWithData(data) {
    const template = document.getElementById('attachment-row-template');
    const container = document.getElementById('attachments-container');
    const clone = template.content.cloneNode(true);
    
    const row = clone.querySelector('.attachment-row');
    row.querySelector('[name="attachment_type"]').value = data.type || '';
    row.querySelector('[name="attachment_name"]').value = data.名称 || '';
    row.querySelector('[name="attachment_level"]').value = data.设备等级 || '';
    row.querySelector('[name="attachment_spec"]').value = data.型号规格 || '';
    row.querySelector('[name="attachment_manufacturer"]').value = data.生产厂家 || '';
    
    // 存储ID用于编辑时更新
    if (data.id) {
        row.dataset.id = data.id;
    }
    
    container.appendChild(clone);
}
```

**步骤5: 修改表单提交逻辑**

在提交前收集附件数据到隐藏字段：

```javascript
document.getElementById('valveForm').addEventListener('submit', function(e) {
    // ... 现有验证逻辑 ...
    
    // 收集附件数据
    const attachments = [];
    document.querySelectorAll('.attachment-row').forEach(function(row) {
        const type = row.querySelector('[name="attachment_type"]').value;
        if (type) {
            attachments.push({
                id: row.dataset.id || null,
                type: type,
                名称: row.querySelector('[name="attachment_name"]').value,
                设备等级: row.querySelector('[name="attachment_level"]').value,
                型号规格: row.querySelector('[name="attachment_spec"]').value,
                生产厂家: row.querySelector('[name="attachment_manufacturer"]').value
            });
        }
    });
    
    // 添加隐藏字段
    let hiddenField = document.getElementById('attachments-data');
    if (!hiddenField) {
        hiddenField = document.createElement('input');
        hiddenField.type = 'hidden';
        hiddenField.id = 'attachments-data';
        hiddenField.name = 'attachments';
        this.appendChild(hiddenField);
    }
    hiddenField.value = JSON.stringify(attachments);
});
```

**步骤6: 运行验证**

打开浏览器访问 `/valve/new` 页面，确认：
- 第6步显示"附件信息"
- 点击"添加附件"按钮可添加新行
- 点击删除按钮可删除行
- 提交表单时附件数据被正确收集

**步骤7: 提交**

```bash
git add templates/valves/form.html
git commit -m "feat: 添加附件功能前端模板"
```

---

### 任务2: 修改后端 - 保存附件数据

**文件:**
- Modify: `app/routes/valves.py:177-236` (new函数)
- Modify: `app/routes/valves.py:276-340` (edit函数)

**步骤1: 在new函数中添加附件保存逻辑**

在 `valve = Valve()` 创建并提交后，添加附件处理代码：

```python
# 处理附件数据
attachments_data = request.form.get('attachments')
if attachments_data:
    import json
    try:
        attachments = json.loads(attachments_data)
        for att in attachments:
            if att.get('type'):  # 只保存有类型的附件
                attachment = ValveAttachment(
                    valve_id=valve.id,
                    type=att.get('type'),
                    名称=att.get('名称', ''),
                    设备等级=att.get('设备等级', ''),
                    型号规格=att.get('型号规格', ''),
                    生产厂家=att.get('生产厂家', '')
                )
                db.session.add(attachment)
    except json.JSONDecodeError:
        pass  # 忽略无效的JSON数据
```

**步骤2: 在edit函数中添加附件更新逻辑**

在编辑提交处理中，添加附件的更新和删除逻辑：

```python
# 处理附件数据
attachments_data = request.form.get('attachments')
if attachments_data:
    import json
    try:
        attachments = json.loads(attachments_data)
        
        # 获取现有附件ID列表
        existing_ids = {att.id for att in valve.attachments}
        submitted_ids = set()
        
        for att in attachments:
            if att.get('type'):  # 只处理有类型的附件
                att_id = att.get('id')
                if att_id:
                    # 更新现有附件
                    attachment = ValveAttachment.query.get(att_id)
                    if attachment:
                        attachment.type = att.get('type')
                        attachment.名称 = att.get('名称', '')
                        attachment.设备等级 = att.get('设备等级', '')
                        attachment.型号规格 = att.get('型号规格', '')
                        attachment.生产厂家 = att.get('生产厂家', '')
                        submitted_ids.add(att_id)
                else:
                    # 创建新附件
                    attachment = ValveAttachment(
                        valve_id=valve.id,
                        type=att.get('type'),
                        名称=att.get('名称', ''),
                        设备等级=att.get('设备等级', ''),
                        型号规格=att.get('型号规格', ''),
                        生产厂家=att.get('生产厂家', '')
                    )
                    db.session.add(attachment)
        
        # 删除未提交的附件
        for att_id in existing_ids - submitted_ids:
            attachment = ValveAttachment.query.get(att_id)
            if attachment:
                db.session.delete(attachment)
    except json.JSONDecodeError:
        pass  # 忽略无效的JSON数据
```

**步骤3: 运行测试**

1. 访问 `/valve/new` 页面
2. 填写表单并在第6步添加附件
3. 提交后检查数据库中是否有附件记录
4. 编辑已存在的台账，确认附件可正确加载和更新

**步骤4: 提交**

```bash
git add app/routes/valves.py
git commit -m "feat: 添加附件功能后端逻辑"
```

---

### 任务3: 修改详情页 - 显示附件

**文件:**
- Modify: `templates/valves/detail.html`

**步骤1: 在详情页中添加附件展示区域**

找到详情页中基础信息和工艺条件之间的位置，添加附件展示：

```html
{% if valve.attachments %}
<div class="form-section">
    <div class="form-section-header">
        <i class="bi bi-paperclip"></i>
        <h5>附件信息</h5>
    </div>
    <div class="form-section-body">
        <div class="row g-3">
            {% for att in valve.attachments %}
            <div class="col-md-4">
                <div class="card h-100">
                    <div class="card-body">
                        <h6 class="card-title">
                            <span class="badge bg-secondary">{{ att.type }}</span>
                        </h6>
                        <p class="card-text mb-1">
                            <strong>名称：</strong>{{ att.名称 or '-' }}
                        </p>
                        <p class="card-text mb-1">
                            <strong>设备等级：</strong>{{ att.设备等级 or '-' }}
                        </p>
                        <p class="card-text mb-1">
                            <strong>型号规格：</strong>{{ att.型号规格 or '-' }}
                        </p>
                        <p class="card-text">
                            <strong>生产厂家：</strong>{{ att.生产厂家 or '-' }}
                        </p>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
{% endif %}
```

**步骤2: 提交**

```bash
git add templates/valves/detail.html
git commit -m "feat: 详情页显示附件信息"
```

---

### 任务4: 整体测试

**步骤1: 测试完整流程**

1. 新建台账 → 添加附件 → 提交 → 验证保存
2. 查看台账详情 → 验证附件显示
3. 编辑台账 → 修改附件 → 验证更新
4. 编辑台账 → 删除部分附件 → 验证删除
5. 新建台账 → 不添加附件 → 验证正常提交

**步骤2: 提交最终版本**

```bash
git add .
git commit -m "feat: 完成附件功能开发"
```
