document.getElementById('selectAll').addEventListener('change', function() {
    document.querySelectorAll('.item-checkbox').forEach(cb => cb.checked = this.checked);
    document.getElementById('selectAllTop').checked = this.checked;
    updateSelectedCount();
});

document.getElementById('selectAllTop').addEventListener('change', function() {
    document.querySelectorAll('.item-checkbox').forEach(cb => cb.checked = this.checked);
    document.getElementById('selectAll').checked = this.checked;
    updateSelectedCount();
});

document.querySelectorAll('.item-checkbox').forEach(cb => {
    cb.addEventListener('change', updateSelectedCount);
});

function updateSelectedCount() {
    const count = document.querySelectorAll('.item-checkbox:checked').length;
    document.getElementById('selectedCount').textContent = count;
}

function batchDelete() {
    const checked = document.querySelectorAll('.item-checkbox:checked');
    if (checked.length === 0) { alert('请先选择要删除的记录'); return; }
    if (confirm('确定要删除选中的 ' + checked.length + ' 条记录吗？')) {
        document.getElementById('batchForm').action = window.batchDeleteUrl;
        document.getElementById('batchForm').submit();
    }
}

function batchExport() {
    const checked = document.querySelectorAll('.item-checkbox:checked');
    if (checked.length === 0) { alert('请先选择要导出的记录'); return; }
    const ids = Array.from(checked).map(cb => cb.value);
    window.location.href = window.batchExportUrl + '?' + ids.map(id => 'ids=' + id).join('&');
}

function batchApprove() {
    const checked = document.querySelectorAll('.item-checkbox:checked');
    if (checked.length === 0) { alert('请先选择要审批的记录'); return; }
    if (confirm('确定要审批选中的 ' + checked.length + ' 条记录吗？')) {
        document.getElementById('batchForm').action = window.batchApproveUrl;
        document.getElementById('batchForm').submit();
    }
}

let currentFilterDropdown = null;

function showFilterDropdown(event, field) {
    event.stopPropagation();
    
    const existingDropdown = document.getElementById('filterDropdown');
    if (existingDropdown) {
        existingDropdown.remove();
    }
    
    const filterOptions = window.filterOptions;
    const activeFilters = window.activeFilters;
    
    if (!filterOptions[field] || filterOptions[field].length === 0) {
        return;
    }
    
    const dropdown = document.createElement('div');
    dropdown.id = 'filterDropdown';
    dropdown.className = 'filter-dropdown';
    dropdown.style.cssText = 'position: absolute; z-index: 9999; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); min-width: 240px; max-width: 320px;';
    
    const rect = event.target.getBoundingClientRect();
    dropdown.style.left = rect.left + 'px';
    dropdown.style.top = (rect.bottom + window.scrollY) + 'px';
    
    let html = `<div class="p-3 border-bottom d-flex justify-content-between align-items-center" style="background: #f8fafc; border-radius: 8px 8px 0 0;">
        <strong style="color: #1e293b; font-size: 14px;">筛选 ${event.target.textContent}</strong>
        <button type="button" class="btn-close btn-sm" onclick="this.closest('#filterDropdown').remove()" style="opacity: 0.5;"></button>
    </div>
    <div class="p-3 pb-2">
        <div class="form-check mb-2 d-flex align-items-center">
            <input type="checkbox" class="form-check-input" id="selectAll_${field}" onchange="toggleAllFilter('${field}', this.checked)" style="width: 16px; height: 16px; margin-right: 8px;">
            <label class="form-check-label" for="selectAll_${field}" style="font-size: 13px; color: #475569;">全选</label>
        </div>
        <div class="filter-options" style="max-height: 280px; overflow-y: auto; padding-right: 4px;">`;
    
    const selectedValues = activeFilters[field] || [];
    
    filterOptions[field].forEach(value => {
        const isChecked = selectedValues.includes(value);
        html += `<div class="form-check d-flex align-items-center py-1" style="min-height: 32px;">
            <input type="checkbox" class="form-check-input filter-option" name="${field}" value="${value}" ${isChecked ? 'checked' : ''} style="width: 16px; height: 16px; margin-right: 8px;">
            <label class="form-check-label" style="word-break: break-all; font-size: 13px; color: #334155;">${value}</label>
        </div>`;
    });
    
    html += `</div></div>
    <div class="p-3 border-top d-flex gap-2" style="border-radius: 0 0 8px 8px; background: #f8fafc;">
        <button class="btn btn-sm flex-grow-1" onclick="clearFilter('${field}')" style="background: #fff; border: 1px solid #e2e8f0; color: #475569; font-size: 13px; padding: 6px 12px;">清除</button>
        <button class="btn btn-sm flex-grow-1" onclick="applyFilter('${field}')" style="background: linear-gradient(135deg, #38b2ac 0%, #2dd4bf 100%); border: none; color: white; font-size: 13px; padding: 6px 12px;">应用</button>
    </div>`;
    
    dropdown.innerHTML = html;
    document.body.appendChild(dropdown);
    
    currentFilterDropdown = dropdown;
    
    document.addEventListener('click', function closeDropdown(e) {
        if (!dropdown.contains(e.target) && !e.target.closest('.filter-header')) {
            dropdown.remove();
            document.removeEventListener('click', closeDropdown);
        }
    });
}

function toggleAllFilter(field, checked) {
    document.querySelectorAll(`.filter-option[name="${field}"]`).forEach(cb => {
        cb.checked = checked;
    });
}

function applyFilter(field) {
    const checked = document.querySelectorAll(`.filter-option[name="${field}"]:checked`);
    const values = Array.from(checked).map(cb => cb.value);
    
    const url = new URL(window.location.href);
    
    const existingParams = url.searchParams.getAll(field);
    existingParams.forEach(() => url.searchParams.delete(field));
    
    values.forEach(v => url.searchParams.append(field, v));
    
    window.location.href = url.toString();
}

function clearFilter(field) {
    const url = new URL(window.location.href);
    url.searchParams.delete(field);
    window.location.href = url.toString();
}

function submitBatchAction(action) {
    const checked = document.querySelectorAll('.item-checkbox:checked');
    if (checked.length === 0) {
        alert('请先选择要操作的记录');
        return;
    }
    
    const confirmMsg = action === 'batch_approve' ? '确定要审批选中的 ' + checked.length + ' 条记录吗？' : '确定要驳回选中的 ' + checked.length + ' 条记录吗？';
    if (!confirm(confirmMsg)) return;
    
    document.getElementById('batchAction').value = action;
    document.getElementById('batchForm').submit();
}
