function handleListFormSubmit(form) {
    if (form.action.includes('reject') && !confirm('确定要驳回吗？')) {
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

function toggleSelectAll() {
    const selectAll = document.getElementById('selectAll');
    const checkboxes = document.querySelectorAll('.ledger-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = selectAll.checked;
    });
    updateSelectedCount();
}

function updateSelectedCount() {
    const checkboxes = document.querySelectorAll('.ledger-checkbox:checked');
    const allCheckboxes = document.querySelectorAll('.ledger-checkbox');
    const selectAll = document.getElementById('selectAll');
    if (allCheckboxes.length > 0 && checkboxes.length === allCheckboxes.length) {
        selectAll.checked = true;
    } else {
        selectAll.checked = false;
    }
}

function getSelectedLedgerIds() {
    const checkboxes = document.querySelectorAll('.ledger-checkbox:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

function getSubmitUrl() {
    return document.querySelector('.list-toolbar').dataset.batchSubmitUrl;
}

function getDeleteUrl() {
    return document.querySelector('.list-toolbar').dataset.batchDeleteUrl;
}

function batchSubmit() {
    const selectedIds = getSelectedLedgerIds();
    if (selectedIds.length === 0) {
        alert('请选择要提交的合集');
        return;
    }
    
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = getSubmitUrl();
    
    selectedIds.forEach(id => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'ledger_ids';
        input.value = id;
        form.appendChild(input);
    });
    
    document.body.appendChild(form);
    form.submit();
}

function batchDelete() {
    const selectedIds = getSelectedLedgerIds();
    if (selectedIds.length === 0) {
        alert('请选择要删除的合集');
        return;
    }
    
    if (!confirm('确定要删除选中的 ' + selectedIds.length + ' 个合集吗？此操作不可恢复！')) {
        return;
    }
    
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = getDeleteUrl();
    
    selectedIds.forEach(id => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'ledger_ids';
        input.value = id;
        form.appendChild(input);
    });
    
    document.body.appendChild(form);
    form.submit();
}
