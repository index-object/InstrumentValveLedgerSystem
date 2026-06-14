(function() {
    'use strict';

    function handleSubmit(btn) {
        var form = btn.closest('form');
        if (!form) return;
        var original = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>上传中...';
        form.submit();
        setTimeout(function() {
            btn.disabled = false;
            btn.innerHTML = original;
        }, 10000);
    }

    document.addEventListener('DOMContentLoaded', function() {
        var modal = document.getElementById('typeModal');
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    e.stopPropagation();
                }
            });
        }

        var importForm = document.getElementById('importForm');
        if (importForm) {
            importForm.addEventListener('submit', function(e) {
                var btn = importForm.querySelector('button[type="submit"]');
                if (btn && !btn.disabled) {
                    setTimeout(function() { handleSubmit(btn); }, 50);
                }
            });
        }

        var executeForm = document.getElementById('executeForm');
        if (executeForm) {
            executeForm.addEventListener('submit', function(e) {
                var btn = executeForm.querySelector('button[type="submit"]');
                if (btn) {
                    btn.disabled = true;
                    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>导入中...';
                }
            });
        }
    });
})();
