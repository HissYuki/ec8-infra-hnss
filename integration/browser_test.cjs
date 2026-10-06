// Execute apenas na integração LOCAL, com Playwright e Chrome disponíveis.
// Credenciais/códigos ficam na memória e nunca são exibidos no relatório.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {execFileSync} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const compose = ['compose','--project-name','hospital-interna','--env-file',path.join(__dirname,'.env'),
  '-f',path.join(root,'rede-interna/docker-compose.yml'),'-f',path.join(root,'rede-interna/compose.local.yaml')];
const prefix = 'hospital_integration_' + crypto.randomBytes(5).toString('hex');
const fixtureSource = fs.readFileSync(path.join(__dirname,'browser_fixture.py'),'utf8');
function fixture(action, role) {
  const result = execFileSync('docker',[...compose,'exec','-T','backend','python','-c',fixtureSource, action,prefix,...(role?[role]:[])],{encoding:'utf8'});
  return JSON.parse(result.trim());
}
(async () => {
  let browser;
  const data = fixture('setup');
  const origin = 'https://localhost:8443';
  try {
    browser = await chromium.launch({headless:true, executablePath:process.argv[2]});
    for (const role of ['PACIENTE','MEDICO','COORDENADOR','ADMIN']) {
      const context = await browser.newContext({ignoreHTTPSErrors:true, timezoneId:'America/Sao_Paulo'});
      const page = await context.newPage();
      page.setDefaultTimeout(20000);
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      const login = role==='ADMIN'?'/admin/login/':role==='PACIENTE'?'/conta/paciente/login/':'/conta/medico/login/';
      const area = role==='ADMIN'?'/admin/':role==='PACIENTE'?'/paciente/':role==='MEDICO'?'/medico/':'/coordenador/';
      assert.equal((await page.goto(origin+login)).status(),200);
      const withoutCsrf = await context.request.post(origin+login,{form:{username:data.users[role],password:data.password}, maxRedirects:0});
      assert.equal(withoutCsrf.status(),403, 'POST sem CSRF foi aceito');
      await page.locator('[name=username]').fill(data.users[role]);
      await page.locator('[name=password]').fill(data.password);
      await page.locator('form input[type=submit], form button[type=submit]').first().click();
      await page.waitForURL('**/conta/mfa/configurar/');
      const blocked = await context.request.get(origin+area,{maxRedirects:0});
      assert.equal(blocked.status(),302);
      assert.match(blocked.headers().location,/mfa\/configurar/);
      const qr = await context.request.get(origin+'/conta/mfa/qr/');
      assert.equal(qr.status(),200);
      assert.match(qr.headers()['cache-control'],/no-store/);
      assert.match(await qr.text(),/<svg/);
      await page.locator('[name=token]').fill('abc');
      await page.locator('form:has([name=token]) button[type=submit]').click();
      assert.match(await page.textContent('body'),/6 dígitos/);
      await page.locator('[name=token]').fill(fixture('token',role));
      await page.locator('form:has([name=token]) button[type=submit]').click();
      await page.locator('.mfa-codes').waitFor();
      assert.equal(await page.locator('.mfa-codes code').count(),10);
      await page.locator('.auth-continue').click();
      await page.waitForURL(origin+area);
      assert.ok((await context.cookies()).filter(c=>['sessionid','csrftoken'].includes(c.name)).every(c=>c.secure));
      if (role==='MEDICO'||role==='COORDENADOR') {
        await page.locator('.fc-dayGridMonth-button').click();
        await page.locator(`.fc-daygrid-day[data-date="${data.date}"] .fc-daygrid-day-number`).click();
        await page.locator('.fc-timeGridDay-view').waitFor();
        await page.locator(role==='MEDICO'?'.evento-exame':'.evento-exame-disponivel').first().waitFor();
        if(role==='MEDICO') {
          await page.locator('.evento-disponivel').first().waitFor();
          await page.locator('.evento-consulta').first().click();
          await page.waitForURL('**/medico/consulta/*/');
          await page.locator('[name=observacoes]').fill('Observação sintética do teste de integração.');
          await page.locator('form:has([name=observacoes]) button[type=submit]').click();
          await page.reload();
          assert.match(await page.locator('[name=observacoes]').inputValue(),/sintética/);
        }
      }
      if(role==='PACIENTE') {
        await page.goto(origin+'/paciente/consultas/');
        await page.locator('#medico-select').selectOption(String(data.doctor));
        await page.locator('.fc-daygrid-day[data-date="'+data.date+'"] .fc-daygrid-day-number').click();
        await page.locator('.fc-timeGridDay-view').waitFor();
        await page.goto(origin+'/paciente/exames/');
        assert.equal((await context.request.get(origin+'/static/js/agendamentos.js')).status(),200);
        await page.goto(origin+'/paciente/dados/');
        await page.locator('[name=email]').fill(prefix+'@example.com');
        await page.locator('form:has([name=email]) button[type=submit]').click();
        assert.match(await page.textContent('body'),/Informações atualizadas com sucesso/);
      }
      for(const asset of ['/static/css/base.css','/static/admin/css/base.css']) {
        assert.equal((await context.request.get(origin+asset)).status(),200);
      }
      assert.deepEqual(errors,[]);
      const csrf = (await context.cookies()).find(c=>c.name==='csrftoken').value;
      const logout = await context.request.post(origin+(role==='ADMIN'?'/admin/logout/':'/conta/logout/'),
        {form:{csrfmiddlewaretoken:csrf},headers:{Origin:origin,Referer:origin+area},maxRedirects:0});
      assert.equal(logout.status(),302);
      assert.match(logout.headers().location,new RegExp(role==='ADMIN'?'admin/login':role==='PACIENTE'?'paciente/login':'medico/login'));
      if(role==='PACIENTE') {
        await page.goto(origin+'/conta/paciente/senha/');
        await page.locator('[name=email]').fill(prefix+'@example.com');
        await page.locator('form:has([name=email]) button[type=submit]').click();
        await page.waitForURL('**/senha/enviada/');
        const logs = execFileSync('docker',[...compose,'logs','--no-color','backend'],{encoding:'utf8'});
        assert.ok(logs.includes('To: '+prefix+'@example.com'), 'Envio não utilizou o novo e-mail');
        const codes = [...logs.matchAll(/Seu código de recuperação de senha é: (\d{6})/g)];
        assert.ok(codes.length);
        await page.locator('[name=code]').fill(codes.at(-1)[1]);
        await page.locator('form:has([name=code]) button[type=submit]').click();
        await page.waitForURL('**/senha/redefinir/');
        const newPassword = crypto.randomBytes(24).toString('base64url');
        await page.locator('[name=new_password1]').fill(newPassword);
        await page.locator('[name=new_password2]').fill(newPassword);
        await page.locator('form:has([name=new_password1]) button[type=submit]').click();
        await page.waitForURL('**/senha/concluida/');
        // A nova senha funciona, mas o reset não libera a área sem MFA.
        await page.goto(origin+login);
        await page.locator('[name=username]').fill(data.users[role]);
        await page.locator('[name=password]').fill(newPassword);
        await page.locator('form input[type=submit], form button[type=submit]').first().click();
        await page.waitForURL('**/conta/mfa/verificar/');
        const stillBlocked = await context.request.get(origin+area,{maxRedirects:0});
        assert.equal(stillBlocked.status(),302);
        assert.match(stillBlocked.headers().location,/mfa\/verificar/);
      }
      console.log(role+': HTTPS, login, CSRF, MFA, área e logout OK.');
      await context.close();
    }
  } finally {
    if(browser) await browser.close();
    fixture('cleanup');
  }
})().catch(e=>{console.error(e.message);process.exitCode=1;});
