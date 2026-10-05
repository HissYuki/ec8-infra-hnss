// Navegação real do FullCalendar com eventos simulados, sem acessar dados clínicos.
// Requer Node.js e Playwright disponíveis no ambiente que executa este teste.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true, executablePath: process.argv[2] });
    try {
        const context = await browser.newContext({ timezoneId: 'America/Sao_Paulo', viewport: { width: 1280, height: 900 } });
        for (const area of ['medico', 'coordenador', 'paciente']) {
            const page = await context.newPage();
            page.setDefaultTimeout(10000);
            const errors = [];
            page.on('pageerror', error => errors.push(error.message));
            page.on('requestfailed', request => console.error('Recurso indisponível:', request.url(), request.failure()?.errorText));
            await page.clock.install({ time: new Date('2026-10-05T12:00:00Z') });
            const events = [
                { id: 'livre', title: 'Horário livre', start: '2026-10-15T09:00:00', classNames: ['evento-disponivel'] },
                { id: 'consulta', title: 'Consulta de teste', start: '2026-10-15T10:00:00', classNames: ['evento-consulta'], url: '/consulta-fixture' },
                { id: 'exame', title: 'Exame de teste', start: '2026-10-15T11:00:00', classNames: ['evento-exame'] },
            ];
            await page.route(url => url.pathname.startsWith('/eventos-fixture'), route => route.fulfill({ json: area === 'paciente' ? { eventos: events } : events }));
            await page.route('**/consulta-fixture', route => route.fulfill({ contentType: 'text/html', body: '<h1>Detalhes da consulta de teste</h1>' }));
            await page.goto('http://localhost:8000/');
            const patient = area === 'paciente';
            const element = patient ? `
                <select id="seletor"><option value="">Selecione</option><option value="1">Médico de teste</option></select>
                <div id="mensagem-calendario"></div><form id="form-agendamento"></form>
                <button id="aba-atuais"></button><button id="aba-passadas"></button>
                <div id="lista-atuais"></div><div id="lista-passados"></div>
                <div data-agendamento data-seletor="seletor" data-url-horarios="/eventos-fixture/0/"
                    data-aba-passados="aba-passadas" data-lista-atuais="lista-atuais" data-lista-passados="lista-passados"></div>`
                : '<div data-agenda data-url-eventos="/eventos-fixture"></div>';
            await page.setContent(`<!doctype html><html><head>
                <link rel="stylesheet" href="http://localhost:8000/static/css/base.css">
                <link rel="stylesheet" href="http://localhost:8000/static/css/calendarios.css">
                ${area === 'coordenador' ? '<link rel="stylesheet" href="http://localhost:8000/static/css/coordenador/agenda.css">' : ''}
                </head><body>${element}
                <script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.19/index.global.min.js"></script>
                <script src="http://localhost:8000/static/js/calendarios.js"></script>
                <script src="http://localhost:8000/static/js/${patient ? 'agendamentos' : 'agendas'}.js"></script>
                </body></html>`, { waitUntil: 'networkidle' });
            if (errors.length) throw new Error(errors.join('\n'));
            if (!patient) {
                const heights = [];
                for (let sample = 0; sample < 3; sample++) {
                    heights.push(await page.locator('[data-agenda]').evaluate(el => el.getBoundingClientRect().height));
                    await page.waitForTimeout(200);
                }
                assert.ok(Math.max(...heights) < 3000, `Altura inicial excessiva: ${heights}`);
                assert.ok(Math.max(...heights) - Math.min(...heights) < 2, `Agenda não estabiliza: ${heights}`);
            }
            await page.locator('.fc-dayGridMonth-button').click();
            if (patient) await page.locator('#seletor').selectOption('1');
            await page.locator('.fc-daygrid-day[data-date="2026-10-15"] .fc-daygrid-day-number').click();
            await page.locator('.fc-timeGridDay-view').waitFor();
            assert.match(await page.locator('.fc-toolbar-title').textContent(), /15/);
            await page.locator('.evento-consulta').first().waitFor();
            if (!patient) {
                assert.equal(await page.locator('.evento-disponivel').count(), 1);
                assert.equal(await page.locator('.evento-exame').count(), 1);
            }
            const overflow = await page.locator('.fc-scroller').evaluateAll(elements => elements.some(el =>
                ['auto', 'scroll'].includes(getComputedStyle(el).overflowY) && el.scrollHeight > el.clientHeight + 2));
            assert.equal(overflow, false, 'Calendário não deve criar segunda rolagem vertical');
            await page.locator('.fc-next-button').click();
            assert.match(await page.locator('.fc-toolbar-title').textContent(), /16/);
            await page.locator('.fc-prev-button').click();
            assert.match(await page.locator('.fc-toolbar-title').textContent(), /15/);
            await page.locator('.fc-today-button').click();
            assert.match(await page.locator('.fc-toolbar-title').textContent(), /5/);
            await page.locator('.fc-dayGridMonth-button').click();
            await page.locator('.fc-dayGridMonth-view').waitFor();
            await page.locator('.fc-daygrid-day[data-date="2026-10-16"] .fc-daygrid-day-frame').click({ position: { x: 5, y: 40 } });
            await page.locator('.fc-timeGridDay-view').waitFor();
            assert.match(await page.locator('.fc-toolbar-title').textContent(), /16/);
            if (area === 'medico') {
                await page.locator('.fc-prev-button').click();
                await page.locator('.evento-consulta').first().click();
                await page.waitForURL('**/consulta-fixture');
                assert.match(await page.locator('h1').textContent(), /Detalhes/);
            }
            assert.deepEqual(errors, []);
            console.log(`${area}: mês/dia, número do dia, próximo/anterior, Hoje, eventos e rolagem OK`);
            await page.close();
        }
        await context.close();
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
