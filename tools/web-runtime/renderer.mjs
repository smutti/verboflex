/** Execute only declarative, registered actions inside the isolated runner. */
import { createServer } from 'node:http';
import { readFile, realpath, stat } from 'node:fs/promises';
import { resolve, sep, extname } from 'node:path';
import { chromium } from 'playwright';

const mime = {'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.png':'image/png','.svg':'image/svg+xml','.woff2':'font/woff2'};
async function serve(directory) {
  const root=await realpath(directory);
  const server=createServer(async(req,res)=>{
    try {
      const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
      const path=await realpath(resolve(root,'.'+(pathname==='/'?'/index.html':pathname)));
      if(!path.startsWith(root+sep)||!(await stat(path)).isFile())throw Error('Invalid path');
      res.setHeader('Content-Type',mime[extname(path)]||'application/octet-stream');
      res.end(await readFile(path));
    } catch {res.writeHead(404);res.end();}
  });
  await new Promise((ok,fail)=>{server.once('error',fail);server.listen(0,'127.0.0.1',ok);});
  return {server,origin:`http://127.0.0.1:${server.address().port}`};
}

export async function capture({directory,scenario,language,catalogs,viewport,output,timeout=30000}) {
  const {server,origin}=await serve(directory);
  let browser;
  const violations=[];
  try {
    browser=await chromium.launch({headless:true});
    const context=await browser.newContext({viewport,locale:language,deviceScaleFactor:1,colorScheme:'light',serviceWorkers:'block',acceptDownloads:false});
    await context.addInitScript(({language})=>{localStorage.setItem('language',language);sessionStorage.setItem('token','synthetic-capture-only');},{language});
    await context.routeWebSocket('**/*', socket => { violations.push('websocket'); socket.close(); });
    await context.route('**/*',async route=>{
      const req=route.request(),url=new URL(req.url());
      if(url.origin!==origin){violations.push('external_request');return route.abort();}
      const catalog=Object.entries(catalogs).find(([path])=>url.pathname===path);
      if(catalog&&req.method()==='GET')return route.fulfill({json:catalog[1]});
      const fixture=scenario.responses?.find(item=>item.path===url.pathname+url.search&&item.method===req.method());
      if(fixture)return route.fulfill({status:fixture.status??200,json:fixture.body});
      if(url.pathname.startsWith('/api/')||req.method()!=='GET'){violations.push('unregistered_request');return route.abort();}
      return route.continue();
    });
    const page=await context.newPage();
    page.setDefaultTimeout(timeout);
    page.on('pageerror',()=>violations.push('page_error'));
    page.on('console',message=>{if(message.type()==='error')violations.push('console_error');});
    page.on('response',response=>{if(response.status()>=400&&!scenario.responses?.some(f=>new URL(response.url()).pathname+new URL(response.url()).search===f.path&&f.status===response.status()))violations.push('asset_failed');});
    await page.clock.install({time:new Date('2026-01-01T12:00:00Z')});
    await page.goto(origin+(scenario.route.startsWith('/')?'':'/')+scenario.route,{waitUntil:'domcontentloaded',timeout});
    await page.locator(scenario.ready).waitFor({state:'visible'});
    for(const step of scenario.actions??[]){
      const element=page.locator(step.selector);
      if(step.action==='click')await element.click();
      else if(step.action==='fill')await element.fill(step.value);
      else if(step.action==='blur')await element.blur();
      else if(step.action==='wait')await element.waitFor({state:'visible'});
      else if(step.action==='assert_disabled'){if(!await element.isDisabled())throw Error('Expected disabled control');}
      else if(step.action==='assert_enabled'){if(!await element.isEnabled())throw Error('Expected enabled control');}
      else throw Error('Unsupported scenario action');
    }
    await page.evaluate(()=>{for(const animation of document.getAnimations()){try{animation.finish();}catch{animation.cancel();}}});
    await page.evaluate(()=>new Promise(requestAnimationFrame));
    const target=page.locator(scenario.target);
    if(await target.count()!==1)throw Error('Ambiguous target');
    await target.waitFor({state:'visible'});
    await target.scrollIntoViewIfNeeded();
    await page.evaluate(()=>document.fonts.ready);
    const text=scenario.target_attribute === 'placeholder' ? await target.getAttribute('placeholder') : await target.innerText();
    if(!text?.trim()||(scenario.target_attribute==='placeholder'&&await target.inputValue()))throw Error('Target text is not visible');
    const bounds=await target.boundingBox();
    if(!bounds||bounds.width<=0||bounds.height<=0)throw Error('Invisible target');
    const visible = await target.evaluate(async element => {
      const rect = element.getBoundingClientRect();
      if (rect.x < 0 || rect.y < 0 || rect.right > innerWidth || rect.bottom > innerHeight) return false;
      // Browser layout knows that body overflow does not clip fixed modal portals.
      const complete = await new Promise(resolve => {
        const observer = new IntersectionObserver(([entry]) => {observer.disconnect();resolve(entry.intersectionRatio >= 0.9999);}, {threshold:[0,1]});
        observer.observe(element);
      });
      const hit=document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2);
      return complete && (hit===element||element.contains(hit));
    });
    if(!visible)throw Error('Clipped or occluded target');
    if(text.includes('{{')||text.includes('}}'))throw Error('Unresolved interpolation');
    if(violations.length)throw Error([...new Set(violations)].join(','));
    await page.screenshot({path:output,animations:'disabled',timeout});
    if(violations.length)throw Error([...new Set(violations)].join(','));
    return {text,regions:[{x:bounds.x/viewport.width,y:bounds.y/viewport.height,width:bounds.width/viewport.width,height:bounds.height/viewport.height}],violations};
  } finally {
    if(browser)await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
}
