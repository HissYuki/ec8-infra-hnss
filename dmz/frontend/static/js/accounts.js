document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.mostrar-senha').forEach(function (button) {
        button.addEventListener('click', function () {
            const input = button.parentElement.querySelector('input');
            const show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            const label = show ? 'Ocultar senha' : 'Mostrar senha';
            button.setAttribute('aria-label', label);
            button.setAttribute('title', label);
        });
    });
});
