(function() {
    'use strict';

    document.addEventListener('DOMContentLoaded', function() {
        var modal = document.getElementById('typeModal');
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    e.stopPropagation();
                }
            });
        }
    });
})();
