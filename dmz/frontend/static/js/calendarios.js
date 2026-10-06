// Opções comuns aos calendários; cada página define apenas suas diferenças.
window.HospitalCalendarios = {
    opcoes: function (semana = true) {
        return {
            locale: 'pt-br',
            timeZone: 'local',
            slotMinTime: '06:00:00',
            slotMaxTime: '20:30:00',
            slotDuration: '00:30:00',
            slotLabelInterval: '00:30:00',
            slotLabelFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
            eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
            allDaySlot: false,
            nowIndicator: true,
            navLinks: true,
            navLinkDayClick: 'timeGridDay',
            dateClick: function (info) {
                if (this.view.type === 'dayGridMonth') {
                    this.changeView('timeGridDay', info.dateStr);
                }
            },
            buttonText: {
                today: 'Hoje', month: 'Mês', ...(semana ? { week: 'Semana' } : {}), day: 'Dia'
            }
        };
    }
};
