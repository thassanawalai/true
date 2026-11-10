// Optional external Playwright runner; no runtime dependency is added to the app.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fixture = JSON.parse(process.env.PHASE3_BROWSER_FIXTURE);
const base = process.env.PORTAL_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE });
const pages = {};
const errors = [];
let passed = 0;
async function check(name, action) { await action(); console.log('PASS:', name); passed++; }
async function shown(locator) { await locator.waitFor({ state: 'visible', timeout: 15000 }); }
async function login(name) {
  const context = await browser.newContext();
  const page = await context.newPage(); pages[name] = page;
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base);
  await page.getByLabel('Select demo user').locator('option[value="' + fixture.users[name].id + '"]').waitFor({ state: 'attached' });
  await page.getByLabel('Select demo user').selectOption(fixture.users[name].id);
  await page.getByRole('button', { name: 'Login', exact: true }).click();
  await shown(page.getByRole('button', { name: 'Logout' }));
  return page;
}
async function read(page, path, data, method = 'GET') {
  const token = await page.evaluate(() => sessionStorage.getItem('demo_token'));
  return page.request.fetch(base + '/api' + path, { method, data, headers: { Authorization: 'Bearer ' + token } });
}
async function selectRoom(page, id) {
  await page.getByLabel('Chat room', { exact: true }).locator('option[value="' + id + '"]').waitFor({ state: 'attached', timeout: 15000 });
  await page.getByLabel('Chat room', { exact: true }).selectOption(id);
  await shown(page.getByRole('region', { name: 'Private conversation' }));
}
async function send(page, message, staff = false) {
  await page.getByLabel('Private chat message').fill(message);
  await page.getByRole('button', { name: staff ? 'Reply' : 'Send message', exact: true }).click();
  await shown(page.getByText(message, { exact: true }));
}
try {
  const a1 = await login('a1');
  let roomId;
  await check('Customer opens private room; AI-first, no automatic ticket', async () => {
    const opened = a1.waitForResponse(response => response.url().endsWith('/api/chat-rooms') && response.request().method() === 'POST');
    await a1.getByRole('button', { name: 'Open private chat' }).click();
    roomId = (await (await opened).json()).id;
    await shown(a1.getByLabel('Private chat message'));
    assert.equal(await a1.getByRole('button', { name: 'Create ticket from chat' }).count(), 0);
    await send(a1, 'private assets question ' + fixture.marker);
    await shown(a1.getByText('No assets found.', { exact: true }));
    const result = await (await read(a1, '/chat-rooms/' + roomId)).json();
    assert.equal(result.ticket_id, null);
    assert.deepEqual(result.messages.map(m => m.role), ['customer', 'assistant']);
    assert.deepEqual(await (await read(a1, '/tickets/')).json(), []);
    await shown(a1.getByText(/expires 30 minutes/));
  });
  const a2 = await login('a2'); const b1 = await login('b1');
  await check('Same-company A2 and cross-company B cannot read/reply/link A1 chat', async () => {
    for (const page of [a2, b1]) {
      const rooms = await (await read(page, '/chat-rooms')).json();
      assert.equal(rooms.some(room => room.id === roomId), false);
      assert.equal((await read(page, '/chat-rooms/' + roomId)).status(), 404);
      assert.equal((await read(page, '/chat-rooms/' + roomId + '/messages', { content: 'steal' }, 'POST')).status(), 404);
      assert.equal((await read(page, '/chat-rooms/' + roomId + '/ticket', { subject: 'steal' }, 'POST')).status(), 404);
      assert.equal(await page.getByLabel('Chat room', { exact: true }).locator('option[value="' + roomId + '"]').count(), 0);
    }
  });
  await check('Unticketed refresh and navigation reconnect within TTL; no browser transcript storage', async () => {
    await a1.reload(); await selectRoom(a1, roomId);
    await shown(a1.getByText('private assets question ' + fixture.marker, { exact: true }));
    await a1.getByRole('button', { name: 'My Company Tickets', exact: true }).click();
    await shown(a1.getByText('No tickets found for this company.'));
    await a1.getByRole('button', { name: 'Chat', exact: true }).click(); await selectRoom(a1, roomId);
    const storage = await a1.evaluate(() => ({ local: { ...localStorage }, session: Object.keys(sessionStorage) }));
    assert.deepEqual(storage.local, {}); assert.deepEqual(storage.session, ['demo_token']);
  });
  const admin = await login('admin'); const support = await login('support');
  await check('SOC ADMIN and SUPPORT see rooms, filter companies, and reply live', async () => {
    for (const [name, page] of [['admin', admin], ['support', support]]) {
      await selectRoom(page, roomId);
      await send(page, 'Live SOC reply ' + name, true);
      await shown(a1.getByText('Live SOC reply ' + name, { exact: true }));
      await page.getByLabel('Customer company').selectOption(fixture.users.b1.company_id);
      assert.equal(await page.getByText('private assets question ' + fixture.marker, { exact: true }).count(), 0);
      const response = await page.waitForResponse(r => r.url().includes('/api/chat-rooms?company_id='));
      assert.equal((await response.json()).some(room => room.id === roomId), false);
      await page.getByLabel('Customer company').selectOption(fixture.users.a1.company_id);
      await selectRoom(page, roomId);
    }
  });
  let ticketId;
  await check('Customer explicitly confirms ticket; full customer/bot/SOC history is linked', async () => {
    await a1.getByRole('button', { name: 'Create ticket from chat' }).click();
    await a1.getByLabel('Chat ticket subject').fill('Browser ticket ' + fixture.marker);
    await a1.getByLabel('Chat ticket description').fill('Synthetic incident description');
    assert.equal((await (await read(a1, '/chat-rooms/' + roomId)).json()).ticket_id, null);
    await a1.getByRole('button', { name: 'Confirm create ticket' }).click();
    await shown(a1.getByText(/Ticket-linked history is saved/));
    const linked = await (await read(a1, '/chat-rooms/' + roomId)).json(); ticketId = linked.ticket_id;
    assert.ok(ticketId); assert.equal(linked.temporary, false); assert.equal(linked.messages.length, 4);
    await a1.getByRole('button', { name: 'My Company Tickets', exact: true }).click();
    await a1.getByRole('cell', { name: 'Browser ticket ' + fixture.marker, exact: true }).click();
    await shown(a1.getByText('Live SOC reply admin', { exact: true }));
    await shown(a1.getByRole('region', { name: 'AI Assessment' }).getByText(/Fallback — SOC review required/));
    await shown(a1.getByText('Synthetic incident description', { exact: true }));
  });
  await check('A2 shares ticket metadata but private transcript stays inaccessible; B cannot see ticket', async () => {
    await a2.getByRole('button', { name: 'My Company Tickets', exact: true }).click();
    await a2.getByRole('cell', { name: 'Browser ticket ' + fixture.marker, exact: true }).click();
    await shown(a2.getByText('No chat history available to this user', { exact: true }));
    assert.equal(await a2.getByText('Live SOC reply admin', { exact: true }).count(), 0);
    assert.equal((await read(a2, '/chat-rooms/by-ticket/' + ticketId)).status(), 404);
    assert.equal((await read(b1, '/tickets/' + ticketId)).status(), 404);
    assert.equal((await read(b1, '/chat-rooms/by-ticket/' + ticketId)).status(), 404);
    await b1.getByRole('button', { name: 'My Company Tickets', exact: true }).click();
    await shown(b1.getByText('No tickets found for this company.'));
  });
  await check('Ticket-linked SOC replies and customer follow-up survive refresh', async () => {
    await send(support, 'Durable SOC reply', true);
    await shown(a1.getByText('Durable SOC reply', { exact: true }));
    await send(a1, 'collector follow-up'); await shown(a1.getByText('No log collectors found.', { exact: true }));
    await a1.reload(); await selectRoom(a1, roomId);
    await shown(a1.getByText('Durable SOC reply', { exact: true }));
    await shown(a1.getByText('collector follow-up', { exact: true }));
  });
  await check('Expired signed session during polling clears room and returns to login', async () => {
    await a1.evaluate(token => sessionStorage.setItem('demo_token', token), fixture.expired_token);
    await shown(a1.getByRole('heading', { name: 'SOC AI Support — Demo Login' }));
    assert.equal(await a1.getByText('Durable SOC reply', { exact: true }).count(), 0);
    assert.equal(await a1.evaluate(() => sessionStorage.getItem('demo_token')), null);
    await shown(a1.getByRole('alert'));
  });
  await check('UI handles a temporary room expiring/unavailable with no retained transcript', async () => {
    await b1.getByRole('button', { name: 'Chat', exact: true }).click();
    const opened = b1.waitForResponse(response => response.url().endsWith('/api/chat-rooms') && response.request().method() === 'POST');
    await b1.getByRole('button', { name: 'Open private chat' }).click();
    const id = (await (await opened).json()).id;
    await shown(b1.getByLabel('Private chat message'));
    await send(b1, 'ephemeral B question');
    assert.equal((await read(b1, '/chat-rooms/' + id, undefined, 'DELETE')).status(), 200);
    await shown(b1.getByRole('alert').filter({ hasText: 'expired or unavailable' }));
    assert.equal(await b1.getByText('ephemeral B question', { exact: true }).count(), 0);
    await b1.getByRole('button', { name: 'Open private chat' }).click();
    await shown(b1.getByLabel('Private chat message'));
  });
  await check('Owner explicitly discards temporary chat with confirmation', async () => {
    await send(b1, 'discard this test message');
    b1.once('dialog', dialog => dialog.accept());
    await b1.getByRole('button', { name: 'Discard temporary chat', exact: true }).click();
    await shown(b1.getByRole('alert'));
    assert.equal(await b1.getByText('discard this test message', { exact: true }).count(), 0);
    await b1.getByRole('button', { name: 'Open private chat' }).click();
    await shown(b1.getByLabel('Private chat message'));
  });
  await check('Failed send shows loading/error, keeps draft and allows retry without creating ticket', async () => {
    let release; const gate = new Promise(resolve => release = resolve);
    await b1.route('**/api/chat-rooms/*/messages', async route => {
      await gate; await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Temporary chat outage' }) });
    });
    await b1.getByLabel('Private chat message').fill('retry assets');
    await b1.getByRole('button', { name: 'Send message', exact: true }).click();
    await shown(b1.getByRole('status').filter({ hasText: 'Sending' }));
    assert.equal(await b1.getByRole('button', { name: 'Send message', exact: true }).isDisabled(), true);
    release(); await shown(b1.getByRole('alert').filter({ hasText: 'Temporary chat outage' }));
    assert.equal(await b1.getByLabel('Private chat message').inputValue(), 'retry assets');
    await b1.unroute('**/api/chat-rooms/*/messages');
    await b1.getByRole('button', { name: 'Send message', exact: true }).click();
    await shown(b1.getByText('No assets found.', { exact: true }));
    assert.deepEqual(await (await read(b1, '/tickets/')).json(), []);
  });
  await check('SOC ticket detail exposes authorized history; assignment/status controls still work', async () => {
    await support.getByRole('button', { name: 'Company Tickets', exact: true }).click();
    await support.getByRole('cell', { name: 'Browser ticket ' + fixture.marker, exact: true }).click();
    await shown(support.getByText('Durable SOC reply', { exact: true }));
    await support.getByRole('button', { name: 'Assign to Me', exact: true }).click();
    await support.getByRole('cell', { name: 'Browser ticket ' + fixture.marker, exact: true }).click();
    const status = support.locator('select').filter({ has: support.locator('option[value="PENDING"]') });
    await status.selectOption('PENDING');
    await support.waitForResponse(response => response.url().endsWith('/status') && response.request().method() === 'PATCH');
    const ticket = await (await read(support, '/tickets/' + ticketId)).json();
    assert.equal(ticket.status, 'PENDING'); assert.equal(ticket.assignee_id, fixture.users.support.id);
  });
  assert.deepEqual(errors, []);
  console.log('Browser flows passed:', passed);
} finally { await browser.close(); }
