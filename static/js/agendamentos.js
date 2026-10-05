document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-agendamento]').forEach(function (element) {
        const config = element.dataset;
        const select = document.getElementById(config.seletor);
        const message = document.getElementById('mensagem-calendario');
        const form = document.getElementById('form-agendamento');
        const calendar = new FullCalendar.Calendar(element, {
            ...HospitalCalendarios.opcoes(false),
            initialView: 'dayGridMonth',
            height: 'auto',
            headerToolbar: {
                left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridDay'
            },
            eventClick: function (info) {
                const time = info.event.start.toLocaleString('pt-BR', {
                    dateStyle: 'short', timeStyle: 'short'
                });
                if (!confirm(config.mensagemConfirmacao + time + '?')) return;
                form.action = config.urlAgendamento.replace('/0/', '/' + info.event.id + '/');
                form.submit();
            }
        });
        calendar.render();

        select.addEventListener('change', function () {
            calendar.removeAllEventSources();
            element.style.display = 'block';
            message.style.display = 'block';
            if (!this.value) {
                message.textContent = config.mensagemSelecao;
                calendar.updateSize();
                return;
            }
            message.textContent = 'Carregando horários disponíveis...';
            const url = config.urlHorarios.replace('/0/', '/' + this.value + '/');
            fetch(url)
                .then(function (response) {
                    if (!response.ok) throw new Error();
                    return response.json();
                })
                .then(function (data) {
                    if (data.bloqueado) {
                        element.style.display = 'none';
                        message.style.display = 'block';
                        message.textContent = data.mensagem;
                        return;
                    }
                    element.style.display = 'block';
                    if (data.eventos.length === 0) {
                        message.style.display = 'block';
                        message.textContent = config.mensagemVazia;
                        calendar.updateSize();
                        return;
                    }
                    message.style.display = 'none';
                    calendar.addEventSource(data.eventos);
                    calendar.updateSize();
                })
                .catch(function () {
                    message.style.display = 'block';
                    message.textContent = 'Não foi possível carregar os horários.';
                });
        });

        const currentTab = document.getElementById('aba-atuais');
        const pastTab = document.getElementById(config.abaPassados);
        const currentList = document.getElementById(config.listaAtuais);
        const pastList = document.getElementById(config.listaPassados);
        currentTab.addEventListener('click', function () {
            currentList.style.display = 'block';
            pastList.style.display = 'none';
            currentTab.classList.add('ativa');
            pastTab.classList.remove('ativa');
        });
        pastTab.addEventListener('click', function () {
            currentList.style.display = 'none';
            pastList.style.display = 'block';
            pastTab.classList.add('ativa');
            currentTab.classList.remove('ativa');
        });
    });
});
