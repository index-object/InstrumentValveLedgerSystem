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

    function initTypeSearch() {
        var inputs = document.querySelectorAll('.type-search-input');
        inputs.forEach(function(input) {
            input.addEventListener('input', function() {
                var keyword = this.value.trim().toLowerCase();
                var targetId = 'typeOptions' + this.getAttribute('data-target');
                var options = document.getElementById(targetId);
                if (!options) return;
                var items = options.querySelectorAll('.type-option');
                var visibleCount = 0;
                items.forEach(function(item) {
                    var label = item.querySelector('.form-check-label');
                    if (!label) return;
                    var text = label.textContent.toLowerCase();
                    if (text.includes(keyword)) {
                        item.style.display = '';
                        visibleCount++;
                    } else {
                        item.style.display = 'none';
                    }
                });
                var noMatch = options.querySelector('.type-search-no-match');
                if (visibleCount === 0) {
                    if (!noMatch) {
                        noMatch = document.createElement('div');
                        noMatch.className = 'type-search-no-match text-center text-muted py-3';
                        noMatch.style.fontSize = '13px';
                        noMatch.innerHTML = '<i class="bi bi-search me-1"></i>没有匹配的设备类型';
                        options.appendChild(noMatch);
                    }
                    noMatch.style.display = '';
                } else {
                    if (noMatch) noMatch.style.display = 'none';
                }
            });
        });
    }

    function initSmartSuggestion() {
        var cards = document.querySelectorAll('.type-select-card');
        cards.forEach(function(card) {
            var headers = card.querySelectorAll('.badge');
            if (headers.length === 0) return;
            var headerTexts = [];
            headers.forEach(function(h) { headerTexts.push(h.textContent.trim().toLowerCase()); });

            var typeMap = {
                '压力': ['pressure_transmitter', 'local_pressure_gauge'],
                '压力变送': 'pressure_transmitter',
                '压力表': 'local_pressure_gauge',
                '温度': ['temperature', 'local_temperature'],
                '温度计': 'local_temperature',
                '热电阻': 'temperature',
                '热电偶': 'temperature',
                '流量': 'flow_meter',
                '液位': ['level_transmitter', 'local_level'],
                '物位': 'level_transmitter',
                '轴系': 'shaft_instrument',
                '振动': 'shaft_instrument',
                '位移': 'shaft_instrument',
                '阀': 'valve',
                '调节阀': 'valve',
                '开关阀': 'valve',
            };

            var suggestedCode = null;
            var highestScore = 0;
            var codeScores = {};
            for (var keyword in typeMap) {
                var matched = headerTexts.some(function(h) { return h.includes(keyword); });
                if (matched) {
                    var codes = Array.isArray(typeMap[keyword]) ? typeMap[keyword] : [typeMap[keyword]];
                    codes.forEach(function(code) {
                        codeScores[code] = (codeScores[code] || 0) + 1;
                        if (codeScores[code] > highestScore) {
                            highestScore = codeScores[code];
                            suggestedCode = code;
                        }
                    });
                }
            }

            if (suggestedCode) {
                var radio = card.querySelector('input[type="radio"][value="' + suggestedCode + '"]');
                if (radio) {
                    radio.checked = true;
                    var label = card.querySelector('label[for="' + radio.id + '"]');
                    if (label) {
                        var suggestionBadge = card.querySelector('.suggestion-badge');
                        if (!suggestionBadge) {
                            suggestionBadge = document.createElement('span');
                            suggestionBadge.className = 'suggestion-badge badge bg-warning text-dark ms-2';
                            suggestionBadge.style.fontSize = '11px';
                            suggestionBadge.textContent = '系统推荐';
                            label.parentNode.appendChild(suggestionBadge);
                        }
                    }
                }
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function() {
        var modal = document.getElementById('typeModal');
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    e.stopPropagation();
                }
            });
            initTypeSearch();
            initSmartSuggestion();
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

        var typeModalForm = document.getElementById('typeModalForm');
        if (typeModalForm) {
            typeModalForm.addEventListener('submit', function(e) {
                var btn = typeModalForm.querySelector('button[type="submit"]');
                if (btn) {
                    btn.disabled = true;
                    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>处理中...';
                }
            });
        }

        var resolveForm = document.getElementById('resolveConflictForm');
        if (resolveForm) {
            resolveForm.addEventListener('submit', function(e) {
                var btn = resolveForm.querySelector('button[type="submit"]');
                if (btn) {
                    btn.disabled = true;
                    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>处理中...';
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
