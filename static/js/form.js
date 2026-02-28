let currentStep = 1;
const totalSteps = 6;

function addAttachment(data = null) {
    const template = document.getElementById('attachment-row-template');
    const clone = template.content.cloneNode(true);
    const container = document.getElementById('attachments-container');
    container.appendChild(clone);
    
    if (data) {
        const row = container.lastElementChild;
        row.querySelector('[name="attachment_type"]').value = data.attachment_type || '';
        row.querySelector('[name="attachment_name"]').value = data.name || '';
        row.querySelector('[name="attachment_grade"]').value = data['设备等级'] || data.device_grade || '';
        row.querySelector('[name="attachment_model"]').value = data.model || '';
        row.querySelector('[name="attachment_manufacturer"]').value = data.manufacturer || '';
    }
}

function removeAttachment(btn) {
    const row = btn.closest('.attachment-row');
    const container = document.getElementById('attachments-container');
    
    row.remove();
    
    if (container.querySelectorAll('.attachment-row').length === 0) {
        addAttachment();
    }
}

function collectAttachments() {
    const container = document.getElementById('attachments-container');
    if (!container) {
        console.error('attachments-container not found');
        return '[]';
    }
    const rows = container.querySelectorAll('.attachment-row');
    const attachments = [];
    rows.forEach(row => {
        const type = row.querySelector('[name="attachment_type"]');
        const name = row.querySelector('[name="attachment_name"]');
        const grade = row.querySelector('[name="attachment_grade"]');
        const model = row.querySelector('[name="attachment_model"]');
        const manufacturer = row.querySelector('[name="attachment_manufacturer"]');
        
        const typeVal = type ? type.value.trim() : '';
        const nameVal = name ? name.value.trim() : '';
        const gradeVal = grade ? grade.value.trim() : '';
        const modelVal = model ? model.value.trim() : '';
        const manufacturerVal = manufacturer ? manufacturer.value.trim() : '';
        
        if (typeVal || nameVal || gradeVal || modelVal || manufacturerVal) {
            attachments.push({
                attachment_type: typeVal,
                name: nameVal,
                device_grade: gradeVal,
                model: modelVal,
                manufacturer: manufacturerVal
            });
        }
    });
    console.log('collectAttachments result:', attachments);
    return JSON.stringify(attachments);
}

document.addEventListener('DOMContentLoaded', function() {
    const existingAttachments = window.existingAttachments || [];
    if (existingAttachments && existingAttachments.length > 0) {
        existingAttachments.forEach(att => addAttachment(att));
    } else {
        addAttachment();
    }
});

function updateProgress() {
    document.querySelectorAll('.step-item').forEach((item, index) => {
        const step = index + 1;
        item.classList.remove('active', 'completed');
        if (step < currentStep) {
            item.classList.add('completed');
        } else if (step === currentStep) {
            item.classList.add('active');
        }
    });
    
    const progress = ((currentStep - 1) / (totalSteps - 1)) * 100;
    document.getElementById('progressBar').style.width = progress + '%';
    
    document.querySelectorAll('.form-step').forEach((step, index) => {
        step.classList.remove('active');
        if (index + 1 === currentStep) {
            step.classList.add('active');
        }
    });
}

function goToStep(step) {
    if (step < 1 || step > totalSteps) return;
    
    if (step > currentStep) {
        const currentStepEl = document.querySelector('.form-step[data-step="' + currentStep + '"]');
        const requiredFields = currentStepEl ? currentStepEl.querySelectorAll('[required]') : [];
        let valid = true;
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                valid = false;
                field.classList.add('is-invalid');
            } else {
                field.classList.remove('is-invalid');
            }
        });
        if (!valid) {
            alert('请填写必填字段');
            return;
        }
    }
    
    currentStep = step;
    updateProgress();
}

let tagCheckTimeout = null;
const tagInput = document.getElementById('tagInput');
if (tagInput) {
    tagInput.addEventListener('blur', function() {
        const tag = this.value.trim();
        if (!tag) return;
        
        const excludeId = window.excludeValveId;
        
        fetch(window.checkTagUrl + "?位号=" + encodeURIComponent(tag) + (excludeId ? "&exclude_id=" + excludeId : ""))
            .then(r => r.json())
            .then(data => {
                if (!data.valid) {
                    this.classList.add('is-invalid');
                    let feedback = document.getElementById('tagFeedback');
                    if (!feedback) {
                        feedback = document.createElement('div');
                        feedback.id = 'tagFeedback';
                        feedback.className = 'invalid-feedback';
                        this.parentNode.appendChild(feedback);
                    }
                    feedback.textContent = data.message;
                    feedback.style.display = 'block';
                } else {
                    this.classList.remove('is-invalid');
                    const feedback = document.getElementById('tagFeedback');
                    if (feedback) feedback.style.display = 'none';
                }
            });
    });
}

document.getElementById('valveForm').addEventListener('submit', function(e) {
    let valveIdInput = document.getElementById('valve-id-input');
    if (!valveIdInput) {
        valveIdInput = document.createElement('input');
        valveIdInput.type = 'hidden';
        valveIdInput.name = 'valve_id';
        valveIdInput.id = 'valve-id-input';
        this.appendChild(valveIdInput);
    }
    valveIdInput.value = window.currentValveId;
    
    let attachmentsInput = document.getElementById('attachments-data');
    if (!attachmentsInput) {
        attachmentsInput = document.createElement('input');
        attachmentsInput.type = 'hidden';
        attachmentsInput.name = 'attachments';
        attachmentsInput.id = 'attachments-data';
        this.appendChild(attachmentsInput);
    }
    try {
        attachmentsInput.value = collectAttachments();
        console.log('Form submit - attachments value:', attachmentsInput.value);
    } catch (err) {
        console.error('collectAttachments error:', err);
        attachmentsInput.value = '[]';
    }
    
    const requiredFields = document.querySelectorAll('[required]');
    let valid = true;
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            valid = false;
            field.classList.add('is-invalid');
        }
    });
    if (!valid) {
        e.preventDefault();
        alert('请填写所有必填字段');
    }
});

document.querySelectorAll('[required]').forEach(field => {
    field.addEventListener('input', function() {
        if (this.value.trim()) {
            this.classList.remove('is-invalid');
        }
    });
});

let autoSaveTimeout = null;
let currentValveId = window.currentValveId;
let currentLedgerId = window.currentLedgerId;

function autoSave() {
    if (autoSaveTimeout) clearTimeout(autoSaveTimeout);
    
    autoSaveTimeout = setTimeout(function() {
        const formData = {};
        document.querySelectorAll('#valveForm input, #valveForm textarea, #valveForm select').forEach(field => {
            if (field.name) {
                formData[field.name] = field.value;
            }
        });
        
        const attachments = collectAttachments();
        
        fetch(window.saveDraftUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                valve_id: currentValveId,
                ledger_id: currentLedgerId,
                formData: formData,
                attachments: attachments
            })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success && data.valve_id) {
                currentValveId = data.valve_id;
                console.log('草稿已自动保存');
            }
        })
        .catch(err => console.error('自动保存失败:', err));
    }, 3000);
}

document.querySelectorAll('#valveForm input, #valveForm textarea, #valveForm select').forEach(field => {
    field.addEventListener('change', autoSave);
    field.addEventListener('keyup', autoSave);
});

updateProgress();
