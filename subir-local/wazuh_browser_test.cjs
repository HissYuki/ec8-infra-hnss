// LOCAL dashboard test; reads password into memory and never prints it.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const env = Object.fromEntries(fs.readFileSync(path.join(__dirname, '.env'), 'utf8')
  .split(/\r?\n/).filter(line => line && !line.startsWith('#') && line.includes('='))
  .map(line => [line.slice(0,line.indexOf('=')), line.slice(line.indexOf('=')+1)]));
let stage = 'launch';
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.argv[2]});
  try {
    const context = await browser.newContext({ignoreHTTPSErrors:true});
    const page = await context.newPage();
    page.setDefaultTimeout(60000);
    stage = 'connect';
    await page.goto('https://localhost:' + (env.WAZUH_DASHBOARD_PORT || '9443'), {waitUntil:'domcontentloaded'});
    stage = 'username';
    await page.locator('input[name=username], input[placeholder="Username"]').first().fill('admin');
    stage = 'password';
    await page.locator('input[type=password]').fill(env.WAZUH_INDEXER_ADMIN_PASSWORD);
    stage = 'submit';
    await page.locator('button[type=submit]').click();
    stage = 'authenticated';
    await page.waitForURL(url => url.pathname.startsWith('/app/') && !url.pathname.includes('/login'));
    await page.waitForLoadState('domcontentloaded');
    await page.getByText('Wazuh', {exact:false}).first().waitFor();
    assert(!page.url().includes('/login'));
    console.log('PASS: Wazuh dashboard HTTPS login in browser.');
  } finally { await browser.close(); }
})().catch(error => { console.error('FAIL: Wazuh dashboard browser validation at ' + stage + ' (' + error.name + ').'); process.exit(1); });
