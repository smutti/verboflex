// Real browser/layout check with synthetic HTTP boundary responses; no external writes.
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium, expect } = require('@playwright/test');
const [base = 'http://127.0.0.1:5179', output = '/tmp/verboflex-team-ui'] = process.argv.slice(2);
if (!['127.0.0.1', 'localhost'].includes(new URL(base).hostname)) throw new Error('Loopback only');
mkdirSync(output, { recursive: true });
const product = '11111111-1111-4111-8111-111111111111';
const owner = '22222222-2222-4222-8222-222222222222';
const member = '33333333-3333-4333-8333-333333333333';
const version = '44444444-4444-4444-8444-444444444444';
const posts = [];
let admin = false;
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  page.setDefaultTimeout(10000);
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let data;
    if (path.endsWith('/auth/refresh')) data = {access_token:'synthetic-session', token_type:'bearer', must_change_password:false};
    else if (path.endsWith('/users/me')) data = {id:owner,email:'owner@example.com',display_name:'Synthetic Owner',roles:admin?['admin']:['viewer','product_manager_reviewer'],must_change_password:false,product_roles:{[product]:['viewer','translator','product_manager_reviewer']},managed_product_ids:[product]};
    else if (path.endsWith('/products/workspace')) data = {items:[{id:product,name:'Synthetic product',imported_scope_count:0,unimported_scope_count:0,last_imported_at:null,coverage:null}],total:1,page:1,has_more:false};
    else if (path.endsWith('/team')) data = {access:{role:admin?'admin':'product_owner',roles:['product_manager_reviewer'],can_manage_team:true},members:[{user_id:owner,email:'owner@example.com',display_name:'Product Owner',role:'product_owner',version,account_active:true},{user_id:member,email:'translator@example.com',display_name:'Synthetic Translator',role:'translator',version,account_active:true}],has_active_owner:true};
    else if (path.endsWith('/team/members') && route.request().method() === 'POST') {
      posts.push(route.request().postDataJSON());
      return route.fulfill({status:201,contentType:'application/json',body:JSON.stringify({user_id:member,email:'new@example.com',account_created:true,temporary_password:'synthetic-temporary-password!'})});
    }
    else if (path.endsWith('/notifications/unread-count')) data = {unread_count:0};
    else if (path.endsWith('/notifications/recent')) data = {items:[],has_more:false};
    else return route.fulfill({status:404,contentType:'application/json',body:'{"detail":"Synthetic fixture route unavailable"}'});
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.goto(`${base}/products/${product}/team`);
  await expect(page.getByRole('heading',{name:'Product team',exact:true})).toBeVisible();
  await expect(page.getByText('Product Owner · Managed by admin')).toBeVisible();
  await expect(page.getByRole('button',{name:'Appoint owner',exact:true})).toHaveCount(0);
  await expect(page.getByRole('combobox',{name:'Collaborator role'}).locator('option')).toHaveCount(3);
  await page.getByLabel('Collaborator email').fill('new@example.com');
  await page.getByLabel('Display name',{exact:true}).fill('New Translator');
  await page.getByRole('button',{name:'Add collaborator',exact:true}).click();
  await expect.poll(()=>posts.length).toBe(1);
  expect(posts[0]).toEqual({email:'new@example.com',display_name:'New Translator',role:'translator'});
  async function capture(name) {
    for (const width of [1280,320]) {
      await page.setViewportSize({width,height:900});
      await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({path:resolve(output,`${name}-${width}.png`),fullPage:true});
    }
  }
  await expect(page.getByRole('dialog',{name:'Temporary password created'})).toBeVisible();
  await expect(page.getByLabel('Temporary password',{exact:true})).toHaveText('synthetic-temporary-password!');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeVisible();
  await capture('temporary-password');
  await page.getByRole('button',{name:'I saved the password'}).click();
  await expect(page.getByText('synthetic-temporary-password!')).toHaveCount(0);
  await capture('owner-team');
  admin = true;
  await page.reload();
  await expect(page.getByRole('button',{name:'Appoint owner',exact:true})).toBeVisible();
  await capture('admin-team');
  console.log('Owner/admin team and temporary credentials: desktop + 320px layouts, provisioning payload, explicit credential dismissal PASS');
} finally { await browser.close(); }
