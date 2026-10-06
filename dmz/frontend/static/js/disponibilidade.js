document.addEventListener('DOMContentLoaded', function () {
    const buttons = document.querySelectorAll('[data-mostrar-aba]');
    buttons.forEach(function (button) {
        button.addEventListener('click', function () {
            buttons.forEach(function (other) {
                const active = other === button;
                document.getElementById(other.dataset.mostrarAba).style.display = active ? 'block' : 'none';
                if (other.dataset.classeAtiva) {
                    other.classList.toggle(other.dataset.classeAtiva, active);
                }
            });
        });
    });
    document.querySelectorAll('[data-filter-date]').forEach(function (field) {
        field.addEventListener('change', function () {
            const url = new URL(window.location.href);
            url.searchParams.set('data', field.value);
            window.location.href = url.toString();
        });
    });
});
