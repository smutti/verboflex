// Built UI/API only. Credentials and translation bodies never log.
import {createRequire} from "node:module";
import {readFileSync,writeFileSync,mkdirSync} from "node:fs";
import {dirname,join,resolve} from "node:path";
import {openNativeZoomBrowser} from "./phase7_zoom_extension/native_zoom.mjs";
import {waitForSubmissionDetail} from "./phase7_browser_readiness.mjs";
const require=createRequire(new URL("../frontend/package.json",import.meta.url));
const {expect}=require("@playwright/test");
const [mode,fixturePath,backend,frontend]=process.argv.slice(2);
const fixture=JSON.parse(readFileSync(fixturePath,"utf8"));
process.umask(0o077);
let browser,page,token,stage="startup",admissionPosts=0;
const evidence=fixture.evidence_dir ?? join(dirname(fixturePath),"screenshots");
const proof={native_zoom:true,surfaces:[],submissions:[],scenarios:[],keyboard:[]};
const check=value=>{if(!value)throw new Error("Contract rejected");};
const statuses={queued:"Queued",reconciling:"Checking submission outcome",blocked:"Needs review",failed:"Submission failed",succeeded:"Pull request opened",needs_attention:"Submission needs attention",resolved:"Submission resolved"};
function save(){writeFileSync(fixturePath,JSON.stringify(fixture),{mode:0o600});writeFileSync(join(evidence,`phase7-browser-${mode==='scenario'?fixture.scenario.name:mode}.json`),JSON.stringify(proof,null,2),{mode:0o600});}
async function api(path){const response=await fetch(`${backend}/api/v1${path}`,{headers:{Authorization:token},signal:AbortSignal.timeout(10000)});check(response.ok);return response.json();}
async function focusWithKeyboard(locator) {
  await expect(locator).toBeVisible();
  for(let count=0;count<150;count++) {
    if(await locator.evaluate(element=>element===document.activeElement))return;
    await page.keyboard.press("Tab");
  }
  throw new Error("Keyboard target unavailable");
}
async function activate(locator,key="Enter") {
  await focusWithKeyboard(locator);
  await page.keyboard.press(key);
}
async function capture(name,surface) {
  check(/^[a-z0-9_-]+$/.test(name) && /^[a-z0-9_-]+$/.test(surface));
  for(const variant of ["zoom200","width320"]) {
    stage=`${name}-${surface}-${variant}`;
    await page.emulateMedia({reducedMotion:variant==="width320"?"reduce":"no-preference"});
    await page.setViewportSize(variant==="zoom200"?{width:1440,height:900}:{width:320,height:720});
    const factor=variant==="zoom200"?2:1;check(await browser.zoom(page,factor)===factor);
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    const dimensions=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio}));
    check(dimensions.scrollWidth<=dimensions.width);if(variant==="width320")check(dimensions.width===320);
    const targetControls=surface==="submission-review"?await page.getByRole("region",{name:"Permitted destinations"}).locator('[data-slot="select-trigger"]').evaluateAll(controls=>controls.map(control=>{
      const valueElement=control.querySelector('[data-slot="select-value"]');
      const label=control.parentElement.querySelector(":scope > p");
      if(!valueElement || !label)return false;
      const box=control.getBoundingClientRect(),value=valueElement.getBoundingClientRect(),parent=control.parentElement.getBoundingClientRect();
      // The current destination card has one label above the selector; obsolete
      // explanatory paragraphs are no longer part of the product UI.
      return value.top>=box.top && value.bottom<=box.bottom && value.left>=box.left && value.right<=box.right
        && label.getBoundingClientRect().bottom<=box.top && box.left>=parent.left && box.right<=parent.right
        && valueElement.scrollHeight<=valueElement.clientHeight+1;
    })):[];
    check(targetControls.every(Boolean));
    const filename=`${name}-${surface}-${variant}.png`;
    const pixels=await browser.screenshot(page,join(evidence,filename));
    check(pixels.pixel_width>=dimensions.width*factor);
    proof.surfaces.push({name,surface,variant,native_zoom:factor,reduced_motion:variant==="width320",...dimensions,...pixels,target_control_count:targetControls.length,target_controls_fit:targetControls.every(Boolean),screenshot:filename});
  }
  await browser.zoom(page,1);await page.setViewportSize({width:1440,height:900});save();
}
async function dirtyEntry(mapping) {
  stage="keyboard-dirty-entry";await candidates(mapping.product);
  let selected;
  for(const group of mapping.groups ?? []){const detail=await api(`/translations/${group.id}`);if(detail.raw_key==="count"){selected=group.id;break;}}
  check(selected);await page.emulateMedia({reducedMotion:"no-preference"});
  await page.goto(`${frontend}/products/${mapping.product}/strings/${selected}`);
  await activate(page.getByRole("button",{name:"Edit translation",exact:true}));
  await page.locator('textarea[id^="translation-proposal-"]').first().fill("Unsaved isolated smoke draft");
  const enter=page.getByRole("button",{name:"Review for submission",exact:true});await activate(enter);
  await expect(page.getByRole("alertdialog")).toBeVisible();await activate(page.getByRole("button",{name:"Keep editing",exact:true}));
  await expect(page.getByRole("alertdialog")).toHaveCount(0);await expect(enter).toBeFocused();
  await page.keyboard.press("Enter");await expect(page.getByRole("alertdialog")).toBeVisible();
  await activate(page.getByRole("button",{name:"Discard changes",exact:true}));
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await expect(page.getByRole("heading",{name:"Change sets",exact:true})).toBeFocused();
  await expect(page.getByRole("button",{name:"Review selected changes (1)",exact:true})).toBeEnabled();
  proof.keyboard.push({dirty_editor:true,keep_editing_focus:true,discard_navigation:true,overlay_unmounted:true,route_focus_preserved:true});save();
}
async function login(role="admin") {
  const user=fixture.users[role];check(user);await page.goto(`${frontend}/login`);
  await page.getByRole("textbox",{name:"Email"}).fill(user.email);
  await page.getByLabel("Password",{exact:true}).fill(user.password);
  for(let attempt=0;attempt<2;attempt++){
    const pending=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith("/auth/token") && r.request().method()==="POST");
    await activate(page.getByRole("button",{name:"Sign in to VerboFlex",exact:true}));
    const response=await pending;
    if(response.status()!==429){check(response.ok());break;}
    check(attempt===0);
    const retry=response.headers()["retry-after"] ?? "";
    const delay=/^\d+$/.test(retry)?Number(retry)*1000:Date.parse(retry)-Date.now();
    check(Number.isFinite(delay) && delay>=0 && delay<=60000);
    stage="login-rate-limit-wait";proof.login_retry_after_honored=true;
    await new Promise(resolve=>setTimeout(resolve,delay+1000));stage="login-retry";
  }
  await expect(page).not.toHaveURL(/\/login$/);
}
async function candidates(product) {
  const response=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith("/change-set-candidates") && r.status()===200);
  await page.goto(`${frontend}/products/${product}/change-sets`);
  const request=await response;token=request.request().headers().authorization;
  const data=await request.json();await expect(page.getByRole("heading",{name:"Change sets",exact:true})).toBeVisible();return data;
}
async function prepare(product,keys,name,targets=[]) {
  stage=`${name}-selection`;const data=await candidates(product);
  const rows=data.items.filter(item=>keys?keys.includes(item.key):item.can_review && item.key!=="markup");
  check(rows.length>0 && rows.every(item=>item.can_review));if(keys)check(rows.length===keys.length);
  for(const row of rows)await activate(page.getByRole("checkbox",{name:`Select ${row.key} (${row.language})`,exact:true}),"Space");
  await capture(name,"product-navigation");await capture(name,"pending-selection");
  stage=`${name}-review`;
  const queued=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith("/submission-reviews") && r.request().method()==="POST");
  await activate(page.getByRole("button",{name:`Review selected changes (${rows.length})`,exact:true}));
  const response=await queued;check(response.status()===202);let review=await response.json();
  await expect(page.getByText("Review ready",{exact:true})).toBeVisible({timeout:90000});
  for(const target of targets) {
    const select=page.getByRole("combobox",{name:new RegExp(`\\(${target.mapping_id}\\)$`)});
    const ready=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith("/submission-reviews") && r.request().method()==="POST");
    await activate(select);await page.getByRole("option",{name:target.target_branch,exact:true}).press("Enter");
    const updated=await ready;check(updated.status()===202);review=await updated.json();
    await expect(page.getByText("Review ready",{exact:true})).toBeVisible({timeout:90000});
    await expect(page.locator('[data-slot="select-content"]')).toHaveCount(0);
  }
  for(const label of ["Load more files","Load more diff entries"])for(let count=0;count<200;count++) {
    const more=page.getByRole("button",{name:label,exact:true});if(!(await more.count()))break;
    await activate(more);await expect(more).toBeEnabled().catch(()=>undefined);
  }
  await capture(name,"submission-review");return {review_id:review.id,proposal_count:rows.length};
}
async function submit(product,{lose=false}={}) {
  const context=stage;const before=admissionPosts;let intercepted;
  if(lose)await page.route("**/api/v1/products/*/submission-batches",async route=>{
    const response=await route.fetch();check(response.status()===202);intercepted=await response.json();await route.abort("failed");
  },{times:1});
  const result=lose?null:page.waitForResponse(r=>new URL(r.url()).pathname.endsWith("/submission-batches") && r.request().method()==="POST");
  const recovery=lose?page.waitForResponse(r=>r.url().includes("/submission-batches/by-key/") && r.status()===200):null;
  stage=`${context}-activate`;
  await activate(page.getByRole("button",{name:/^Create(?: \d+)? pull requests?$/}));
  let batch;
  if(lose){
    stage=`${context}-automatic-key-recovery`;
    batch=await (await recovery).json();check(batch.id===intercepted.id && batch.request_key===intercepted.request_key);
  }else{stage=`${context}-acceptance-response`;const response=await result;check(response.status()===202);batch=await response.json();}
  stage=`${context}-queued-focus`;
  await expect(page.getByRole("heading",{name:"Submission queued",exact:true})).toBeFocused();
  stage=`${context}-single-admission`;
  check(admissionPosts===before+1 && batch.product_id===product && batch.groups.length>0);return batch;
}
function sanitized(group){return Object.fromEntries(["id","batch_id","status","stage","attempt","repository_id","workspace","repository_slug","source_branch","target_branch","target_head","branch_commit","commit_hash","pr_id","pr_url","pr_state","proposal_count","value_count","file_count","error_code"].map(key=>[key,group[key]]));}
async function detail(product,id,name,{expected="succeeded",wait=true,visual=true}={}) {
  stage=`${name}-detail`;await page.goto(`${frontend}/products/${product}/change-sets/${id}`);
  await expect(page.getByRole("heading",{name:"Change set",exact:true})).toBeFocused();
  if(wait)await expect.poll(async()=>(await api(`/products/${product}/change-sets/${id}`)).status,{timeout:90000,intervals:[500,1000,2000]}).toBe(expected);
  await page.reload();const record=await api(`/products/${product}/change-sets/${id}`);if(expected)check(record.status===expected);
  if(statuses[record.status])await expect(page.getByRole("heading",{name:statuses[record.status],exact:true})).toBeVisible();
  if(record.pr_id!==null){
    const expectedUrl=`https://bitbucket.org/${record.workspace}/${record.repository_slug}/pull-requests/${record.pr_id}`;check(record.pr_url===expectedUrl);
    const link=page.getByRole("link",{name:`Open pull request #${record.pr_id} (opens in a new tab)`,exact:true}).first();
    await expect(link).toHaveAttribute("href",expectedUrl);await expect(link).toHaveAttribute("rel","noopener noreferrer");
  }
  if(visual){await waitForSubmissionDetail(page);await capture(name,"submission-detail");}
  await activate(page.getByRole("link",{name:"Back to submission history",exact:true}));
  await expect(page.locator(`#history-${id}`)).toBeFocused();if(visual)await capture(name,"submission-history");
  await page.reload();await expect(page.locator(`#history-${id}`)).toBeVisible();return sanitized(record);
}
async function reviewOnly() {
  const mapping=fixture.mappings.find(item=>item.name==="android_xml") ?? fixture.mappings[0];
  const queued=await prepare(mapping.product,["count","items"],"review-only");
  await expect(page.getByRole("region",{name:"Selected changes review"})).toContainText("P6 revised è");
  await expect(page.getByLabel("Review totals",{exact:true})).toContainText("4 values");
  await expect(page.getByRole("button",{name:"Create pull request",exact:true})).toBeEnabled();
  await page.reload();await expect(page.getByRole("heading",{name:"No changes selected",exact:true})).toBeVisible();
  check((await api(`/products/${mapping.product}/submission-reviews/${queued.review_id}`)).state==="ready");
  check(admissionPosts===0);proof.review_only=true;save();
  console.log("phase7 review tracer: PASS proposals=2 values=4 files=1 real_worker=true durable_server_review=true memory_only_reload=true provider_writes=audited_by_lifecycle");
}
async function happy() {
  check(fixture.mappings.length===5);if(typeof fixture.phase7!=="object" || !fixture.phase7)fixture.phase7={};fixture.phase7.submissions=[];
  await dirtyEntry(fixture.mappings.find(mapping=>mapping.name==="android_xml"));
  for(const mapping of fixture.mappings){
    const prepared=await prepare(mapping.product,mapping.select_keys,mapping.name,mapping.targets ?? []);stage=`${mapping.name}-submit`;
    const batch=await submit(mapping.product,{lose:mapping.name==="json"});
    const entry={name:mapping.name,product:mapping.product,...prepared,batch_id:batch.id,accepted_response_loss:mapping.name==="json",groups:[]};
    for(const group of batch.groups)entry.groups.push(await detail(mapping.product,group.id,mapping.name));
    fixture.phase7.submissions.push(entry);proof.submissions.push(entry);save();
  }
  if(fixture.http_configuration)await revokedDirtyEditor();
  check(admissionPosts===5);console.log("phase7 submit browser: PASS products=5 accepted_response_loss=true native_zoom=200 width=320 provider_effects=audited_by_lifecycle");
}
async function revokedDirtyEditor() {
  stage="revoked-dirty-editor";
  const mapping=fixture.mappings.find(item=>item.name==="android_xml");
  await candidates(mapping.product);
  let selected;
  for(const group of mapping.groups){if((await api(`/translations/${group.id}`)).raw_key==="count"){selected=group.id;break;}}
  check(selected);
  const before=(await api(`/translations/${selected}`)).pending_change;
  await page.goto(`${frontend}/products/${mapping.product}/strings/${selected}`);
  await activate(page.getByRole("button",{name:"Edit translation",exact:true}));
  await page.locator('textarea[id^="translation-proposal-"]').first().fill("Unsaved revoked-session draft");
  // Settle editor suggestion/context reads before revoking: this case must
  // exercise the rejected save, rather than race an unrelated background read.
  const suggestions=page.getByRole("complementary",{name:"Translation suggestions",exact:true});
  if(await suggestions.count()){
    await expect(suggestions.getByRole("button",{name:"Refresh suggestions",exact:true})).toBeEnabled();
    await expect(suggestions.getByText("Checking terms…",{exact:true})).toHaveCount(0);
  }
  const saveButton=page.getByRole("button",{name:"Save translation",exact:true});
  await expect(saveButton).toBeEnabled();
  await focusWithKeyboard(saveButton);
  stage="revoked-dirty-editor-logout";
  // Revoke the real cookie-backed session outside the SPA. Its in-memory UI
  // remains open until an authenticated request is rejected by the API.
  const revoked=await browser.context.request.post(`${backend}/api/v1/auth/logout`,{headers:{Origin:frontend}});
  check(revoked.status()===204);
  stage="revoked-dirty-editor-save";
  const [rejected]=await Promise.all([
    page.waitForResponse(response=>response.request().method()==="PUT" && new URL(response.url()).pathname===`/api/v1/translations/${selected}/proposal`),
    page.keyboard.press("Enter"),
  ]);
  check(rejected.status()===401);
  await expect(page.getByRole("button",{name:"Sign in to VerboFlex",exact:true})).toBeVisible();
  await expect(page.locator('textarea[id^="translation-proposal-"]')).toHaveCount(0);
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  stage="revoked-dirty-editor-sign-in";
  await login();await candidates(mapping.product);
  const after=(await api(`/translations/${selected}`)).pending_change;
  check(JSON.stringify(before)===JSON.stringify(after));
  proof.revoked_session={http_status:401,editor_removed:true,dirty_overlay_removed:true,proposal_unchanged:true};save();
}
async function scenario() {
  const task=fixture.scenario;check(task && /^[a-z0-9_-]+$/.test(task.name));let result={name:task.name,product:task.product};
  if(task.action==="configure-branches"){
    stage="configure-approval-branches";
    await page.goto(`${frontend}/admin/products/${task.product}/branches`);
    await expect(page.getByRole("heading",{name:"Approval branches",exact:true})).toBeVisible();
    await page.getByLabel("Translation source",{exact:true}).selectOption(task.mapping);
    await page.getByLabel("Working branch",{exact:true}).fill(task.work_branch);
    await page.getByLabel("PR destination",{exact:true}).fill(task.target_branch);
    await capture(task.name,"branch-settings");
    await activate(page.getByRole("button",{name:"Enable approval commits",exact:true}));
    await expect(page.getByText("Approval commits enabled. The next approval will be saved on the working branch.",{exact:true})).toBeVisible();
    result={...result,configured_in_browser:true,working_branch:task.work_branch,target_branch:task.target_branch};
  }else if(task.action==="branch-workflow"){
    stage="approval-branch-history";
    await page.goto(`${frontend}/products/${task.product}/change-sets`);
    await expect(page.getByRole("heading",{name:"Approved changes",exact:true})).toBeVisible();
    await expect(page.getByRole("link",{name:/^Commit /}).first()).toBeVisible();
    await capture(task.name,"approval-commits");
    await activate(page.getByRole("button",{name:"Create pull request",exact:true}));
    await expect(page.getByText("Create a PR from feature/verboflex to master?",{exact:true})).toBeVisible();
    await activate(page.getByRole("button",{name:"Confirm pull request",exact:true}));
    await expect(page.getByRole("link",{name:"Open pull request",exact:true})).toBeVisible({timeout:120000});
    await capture(task.name,"approval-pull-request");
    result={...result,approved_commits:true,explicit_pull_request:true};
  }else if(task.action==="inspect-workspace"){
    stage=`${task.name}-workspace`;const before=admissionPosts;const data=await candidates(task.product);
    if(task.expected_read_only){
      check(data.can_request_review===false);
      await expect(page.getByText("Submission access is read-only",{exact:true})).toBeVisible();
      await expect(page.getByRole("checkbox")).toHaveCount(0);
      await expect(page.getByRole("button",{name:/Review selected changes/})).toHaveCount(0);
    }
    if(task.expected_empty){stage=`${task.name}-empty-candidates`;check(data.items.length===0);await expect(page.getByRole("heading",{name:"No approved changes ready",exact:true})).toBeVisible();}
    if(task.visual!==false)await capture(task.name,"pending-selection");
    if(task.expected_history_empty){
      stage=`${task.name}-empty-history`;
      await activate(page.getByRole("button",{name:"Submission history",exact:true}));
      await expect(page.getByRole("heading",{name:"No submissions yet",exact:true})).toBeVisible();
      if(task.visual!==false)await capture(task.name,"submission-history");
    }
    check(admissionPosts===before);result={...result,read_only:task.expected_read_only===true,empty:task.expected_empty===true,history_empty:task.expected_history_empty===true,admissions:0};
  }else if(task.action==="submit"){
    const prepared=await prepare(task.product,task.select_keys,task.name,task.targets ?? []);
    const batch=await submit(task.product,{lose:task.lose_acceptance_response===true});result={...result,...prepared,batch_id:batch.id,groups:[]};
    for(const group of batch.groups)result.groups.push(await detail(task.product,group.id,task.name,{expected:task.expected_status ?? "succeeded",wait:task.wait!==false,visual:task.visual!==false}));
  }else{
    const data=await candidates(task.product);if(task.role==="viewer")check(data.can_request_review===false);await page.goto(`${frontend}/products/${task.product}/change-sets/${task.group_id}`);
    await expect(page.getByRole("heading",{name:"Change set",exact:true})).toBeFocused();
    if(task.expected_can_retry!==undefined)await expect(page.getByRole("button",{name:"Retry submission",exact:true})).toHaveCount(task.expected_can_retry?1:0);
    if(task.expected_can_reconcile!==undefined)await expect(page.getByRole("button",{name:"Check status",exact:true})).toHaveCount(task.expected_can_reconcile?1:0);
    if(task.action==="retry" || task.action==="reconcile"){
      // Navigation aborts this component's pending action. Observe acceptance
      // before leaving the page, as we already do for initial submission.
      stage=`${task.name}-${task.action}-acceptance`;
      const before=await api(`/products/${task.product}/change-sets/${task.group_id}`);
      const accepted=page.waitForResponse(response=>response.request().method()==="POST" && new URL(response.url()).pathname===`/api/v1/products/${task.product}/change-sets/${task.group_id}/${task.action}`);
      await activate(page.getByRole("button",{name:task.action==="retry"?"Retry submission":"Check status",exact:true}));
      const response=await accepted;check(response.status()===202);
      const record=await response.json();check(record.id===task.group_id && record.batch_id===before.batch_id && record.attempt===before.attempt+1);
    }else check(task.action==="inspect");
    result.groups=[await detail(task.product,task.group_id,task.name,{expected:task.expected_status ?? null,wait:task.wait===true,visual:task.visual!==false})];
  }
  fixture.phase7 ??= {};fixture.phase7.scenarios ??= {};fixture.phase7.scenarios[task.name]=result;proof.scenarios.push(result);save();
  console.log("phase7 scenario browser: PASS durable_identity=true provider_effects=audited_by_lifecycle");
}
try {
  check(["verify","verify-review","scenario"].includes(mode));
  for(const address of [backend,frontend]){const url=new URL(address);check(url.protocol==="http:" && ["127.0.0.1","localhost"].includes(url.hostname));}
  mkdirSync(evidence,{recursive:true,mode:0o700});browser=await openNativeZoomBrowser({runtimeDir:dirname(resolve(fixturePath))});page=await browser.context.newPage();page.setDefaultTimeout(20000);
  page.on("request",request=>{if(request.method()==="POST" && new URL(request.url()).pathname.endsWith("/submission-batches"))admissionPosts++;});
  stage="login";await login(fixture.scenario?.role ?? "admin");
  if(mode==="scenario")await scenario();else if(mode==="verify-review" || (fixture.profile!==7 && fixture.phase7!==true))await reviewOnly();else await happy();
}catch(error){
  const lines=Array.from(String(error?.stack??"").matchAll(/\.mjs:(\d+):\d+/g),match=>match[1]).join("-");
  proof.failure={stage,lines,error_name:/^[A-Za-z]+$/.test(error?.name??"")?error.name:"Error"};
  save();
  console.error(`phase7 smoke failed: ${stage}${lines?"-lines"+lines:""}`);
  process.exitCode=1;
}finally{await browser?.close();}
