function handleFormSubmit(form) {
    if (form.action.includes('reject') && !confirm('确定要驳回所有待审批的台账内容吗？')) {
        return false;
    }
    fetch(form.action, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new FormData(form)
    }).then(response => {
        window.location.reload();
    });
    return false;
}

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

function submitBatchAction(action) {
    const checked = document.querySelectorAll('.item-checkbox:checked');
    if (checked.length === 0) {
        alert('请先选择要操作的记录');
        return;
    }
    
    const confirmMsg = action === 'batch_approve' ? '确定要审批选中的 ' + checked.length + ' 条记录吗？' : '确定要驳回选中的 ' + checked.length + ' 条记录吗？';
    if (!confirm(confirmMsg)) return;
    
    document.getElementById('actionInput').value = action;
    document.getElementById('valveForm').action = window.ledgerDetailUrl;
    document.getElementById('valveForm').submit();
}
