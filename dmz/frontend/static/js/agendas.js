document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-agenda]').forEach(function (element) {
        const options = {
            ...HospitalCalendarios.opcoes(),
            initialView: 'timeGridWeek',
            height: 'auto',
            expandRows: true,
            headerToolbar: {
                left: 'prev,next today', center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay'
            },
            events: element.dataset.urlEventos
        };
        if (element.dataset.primeiroDia !== undefined) {
            options.firstDay = Number(element.dataset.primeiroDia);
        }
        if (element.dataset.cursor) {
            options.eventDidMount = function (info) {
                info.el.style.cursor = element.dataset.cursor;
            };
        }
        new FullCalendar.Calendar(element, options).render();
    });
});
