// Built UI and real API only. Logs never contain credentials or translation text.
import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
const require = createRequire(new URL("../frontend/package.json", import.meta.url));
const { chromium, expect } = require("@playwright/test");
const [mode, fixturePath, backend, frontend] = process.argv.slice(2);
const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
let stage = "startup";
let browser;
function check(value) { if (!value) throw new Error("Contract rejected"); }
async function api(path, token, method = "GET") {
  const response = await fetch(`${backend}/api/v1${path}`, {method,
    signal: AbortSignal.timeout(10000), headers: {Authorization: `Bearer ${token}`}});
  check(response.ok);
  return response.json();
}
try {
  const user = fixture.users.admin;
  const login = await fetch(`${backend}/api/v1/auth/token`, {method: "POST",
    signal: AbortSignal.timeout(10000), headers: {"Content-Type": "application/x-www-form-urlencoded"},
    body: new URLSearchParams({username: user.email, password: user.password})});
  check(login.status === 200);
  const token = (await login.json()).access_token;
  if (mode === "enqueue") {
    for (const mapping of fixture.mappings) {
      stage = `enqueue-${mapping.name}`;
      const job = await api(`/admin/products/${mapping.product}/published/mappings/${mapping.mapping}/imports`, token, "POST");
      check(job.state === "queued");
      mapping.job = job.id;
    }
    writeFileSync(fixturePath, JSON.stringify(fixture), {mode: 0o600});
  } else if (mode === "verify") {
    browser = await chromium.launch({headless: true});
    stage = "browser-login";
    const page = await browser.newPage({viewport: {width: 1440, height: 900}, reducedMotion: "reduce"});
    page.setDefaultTimeout(15000);
    await page.goto(`${frontend}/login`);
    await page.getByRole("textbox", {name: "Email"}).fill(user.email);
    await page.getByLabel("Password", {exact: true}).fill(user.password);
    await page.getByRole("button", {name: "Sign in to VerboFlex", exact: true}).click();
    await expect(page).not.toHaveURL(/\/login$/);
    let approved = 0;
    for (const mapping of fixture.mappings) {
      stage = `import-${mapping.name}`;
      const deadline = Date.now() + 120000;
      let job;
      do {
        job = await api(`/admin/products/${mapping.product}/imports/${mapping.job}`, token);
        if (!["queued", "running"].includes(job.state)) break;
        await new Promise(resolve => setTimeout(resolve, 500));
      } while (Date.now() < deadline);
      check(job.state === "current" && job.dataset_status === "active");
      stage = `search-${mapping.name}`;
      const search = await api(`/translations?product_id=${mapping.product}&language=it&page_size=50&q=P6%20old`, token);
      check(search.items.length > 0);
      mapping.groups = [];
      for (const group of search.items) {
        const detail = await api(`/translations/${group.id}`, token);
        stage = `edit-${mapping.name}`;
        await page.goto(`${frontend}/translations/${group.id}`);
        await page.getByRole("button", {name: "Edit translation", exact: true}).click();
        const editors = page.locator('textarea[id^="translation-proposal-"]');
        await expect(editors).toHaveCount(detail.values.length);
        const count = await editors.count();
        check(count === detail.values.length);
        for (let index = 0; index < count; index++) await editors.nth(index).fill("P6 revised è");
        stage = `save-${mapping.name}`;
        await page.getByRole("button", {name: "Save translation", exact: true}).click();
        await expect(page.getByRole("region", {name: "Pending proposal"})).toContainText("P6 revised è");
        if(fixture.http_configuration && mapping.groups.length===0){
          stage=`comment-${mapping.name}`;
          await page.getByRole("textbox",{name:"Add a comment",exact:true}).fill("Ready for review.");
          const posted=page.waitForResponse(response=>response.request().method()==="POST" && new URL(response.url()).pathname===`/api/v1/translations/${group.id}/comments`);
          await page.getByRole("button",{name:"Post comment",exact:true}).click();
          const response=await posted;check(response.status()===201);
          const comment=await response.json();
          check(comment.author.id===fixture.actor_id && comment.created_at && comment.current_version===1);
          await expect(page.getByText("Ready for review.",{exact:true})).toBeVisible();
          const persisted=await api(`/translations/${group.id}/comments`,token);
          check(persisted.items.some(item=>item.id===comment.id && item.body==="Ready for review."));
          mapping.comment_id=comment.id;
        }
        stage = `approve-${mapping.name}`;
        await page.getByRole("button", {name: "Approve translation", exact: true}).click();
        await expect(page.getByRole("button", {name: "Return to Draft", exact: true})).toBeVisible();
        await page.reload();
        const fresh = await api(`/translations/${group.id}`, token);
        check(fresh.pending_change.state === "approved");
        check(fresh.pending_change.values.length === detail.values.length);
        check(fresh.pending_change.values.every(v => v.text === "P6 revised è"));
        check(fresh.values.every((v, index) => v.translated_text === detail.values[index].translated_text));
        mapping.groups.push({id: group.id, version: fresh.pending_change.version});
        approved++;
      }
    }
    check(approved === 9);
    writeFileSync(fixturePath, JSON.stringify(fixture), {mode: 0o600});
    console.log("phase6 browser: PASS approved_groups=9 formats=4");
  } else throw new Error("Unknown operation");
} catch {
  console.error(`phase6 smoke failed: ${stage}`);
  process.exitCode = 1;
} finally {
  await browser?.close();
}
