// Comportamentos compartilhados. As mensagens e URLs permanecem nos templates.
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-confirm-submit]').forEach(function (form) {
        form.addEventListener('submit', function (event) {
            if (!confirm(form.dataset.confirmSubmit)) event.preventDefault();
        });
    });
    document.querySelectorAll('[data-confirm-click]').forEach(function (button) {
        button.addEventListener('click', function (event) {
            if (!confirm(button.dataset.confirmClick)) event.preventDefault();
        });
    });
    document.querySelectorAll('[data-submit-on-change]').forEach(function (field) {
        field.addEventListener('change', function () { field.form.submit(); });
    });
});
