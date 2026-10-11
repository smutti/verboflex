// Official APIs: playwright.dev/docs/chrome-extensions and
// developer.chrome.com/docs/extensions/reference/api/tabs#method-setZoom.
import { createRequire } from "node:module";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, realpathSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "node:http";
const require = createRequire(new URL("../../frontend/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

export async function openNativeZoomBrowser({runtimeDir=tmpdir()}={}) {
  const root = mkdtempSync(join(realpathSync(runtimeDir), "verboflex-p7-browser-"));
  let context,launching,closing,terminating=false;
  const handlers=new Map();
  function close(){
    return closing ??= (async()=>{
      try {
        // A termination arriving during launch must await the owned browser
        // process before closing/reaping it; deleting its profile alone leaks it.
        const launched=await launching?.catch(()=>undefined);
        await (context ?? launched)?.close();
      }finally{
        rmSync(root,{recursive:true,force:true});
        for(const [signal,handler] of handlers)process.removeListener(signal,handler);
      }
    })();
  }
  for(const [signal,code] of [["SIGINT",130],["SIGTERM",143],["SIGHUP",129]]){
    const handler=()=>{
      if(terminating)return;terminating=true;
      void close().finally(()=>process.exit(code));
    };
    handlers.set(signal,handler);process.on(signal,handler);
  }
  try {
    const extension = join(root,"extension"); mkdirSync(extension,{mode:0o700});
    writeFileSync(join(extension,"manifest.json"),JSON.stringify({manifest_version:3,name:"VerboFlex isolated zoom proof",version:"1.0.0",permissions:["tabs"],background:{service_worker:"worker.js"}}),{mode:0o600});
    writeFileSync(join(extension,"worker.js"),"chrome.runtime.onInstalled.addListener(() => {});",{mode:0o600});
    launching=chromium.launchPersistentContext(join(root,"profile"),{channel:"chromium",headless:true,handleSIGINT:false,handleSIGTERM:false,handleSIGHUP:false,viewport:{width:1440,height:900},reducedMotion:"no-preference",args:[`--disable-extensions-except=${extension}`,`--load-extension=${extension}`]});
    context = await launching;
    const worker = context.serviceWorkers()[0] ?? await context.waitForEvent("serviceworker",{timeout:15000});
    return {context,
      async zoom(page,factor) {
        const actual = await worker.evaluate(async ({url,factor})=>{
          const tabs=await chrome.tabs.query({});
          const tab=tabs.find((candidate)=>candidate.url===url);
          if(!tab?.id)throw new Error("Zoom tab absent");
          await chrome.tabs.setZoomSettings(tab.id,{mode:"automatic",scope:"per-tab"});
          await chrome.tabs.setZoom(tab.id,factor);
          return chrome.tabs.getZoom(tab.id);
        },{url:page.url(),factor});
        // tabs.setZoom resolves before renderer metrics necessarily reflect the
        // new scale. Wait for the requested viewport/zoom before measuring it.
        const viewport=page.viewportSize();
        if(viewport)await page.waitForFunction(
          ({width,factor})=>Math.abs(innerWidth-width/factor)<=1 && Math.abs(devicePixelRatio-factor)<0.01,
          {width:viewport.width,factor},{timeout:10000},
        );
        return actual;
      },
      async screenshot(page,path) {
        // Native tab zoom makes CDP's device-independent content dimensions
        // differ from CSS dimensions. Playwright fullPage crops to the latter.
        const session=await context.newCDPSession(page);
        try {
          for(let attempt=0;attempt<3;attempt++){
            const {contentSize}=await session.send("Page.getLayoutMetrics");
            const {data}=await session.send("Page.captureScreenshot",{format:"png",captureBeyondViewport:true,clip:{x:0,y:0,width:Math.ceil(contentSize.width),height:Math.ceil(contentSize.height),scale:1}});
            const after=(await session.send("Page.getLayoutMetrics")).contentSize;
            if(contentSize.width!==after.width || contentSize.height!==after.height){
              await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
              continue;
            }
            const bytes=Buffer.from(data,"base64");
            if(bytes.readUInt32BE(16)!==Math.ceil(contentSize.width) || bytes.readUInt32BE(20)!==Math.ceil(contentSize.height))throw new Error("Capture dimensions rejected");
            writeFileSync(path,bytes,{mode:0o600});
            return {pixel_width:bytes.readUInt32BE(16),pixel_height:bytes.readUInt32BE(20)};
          }
          throw new Error("Capture layout remained unstable");
        }finally{await session.detach();}
      },
      close,
    };
  }catch(error){await close();throw error;}
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const server=createServer((_req,res)=>{res.end('<!doctype html><button>Native zoom proof</button>');});
  let browser;
  let observed="startup";
  try {
    await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
    browser=await openNativeZoomBrowser();const page=await browser.context.newPage();
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    const before=await page.evaluate(()=>({width:innerWidth,dpr:devicePixelRatio}));
    const zoom=await browser.zoom(page,2);
    const after=await page.evaluate(()=>({width:innerWidth,dpr:devicePixelRatio}));
    observed=`factor-${zoom}-width-${after.width}-dpr-${after.dpr}`;
    if(zoom!==2 || after.dpr!==before.dpr*2 || after.width>before.width/2+1)throw new Error("Native zoom contract failed");
    console.log("phase7 native zoom: PASS factor=2 extension_api=true layout_reflow=true");
  }catch{console.error(`phase7 native zoom: FAIL ${observed}`);process.exitCode=1;}
  finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
}
