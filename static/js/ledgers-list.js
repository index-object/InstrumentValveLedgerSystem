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
