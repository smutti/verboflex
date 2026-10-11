import assert from "node:assert/strict";
import {spawn, execFileSync} from "node:child_process";
import {existsSync, mkdtempSync, readdirSync, rmSync, realpathSync} from "node:fs";
import {tmpdir} from "node:os";
import {join, dirname, resolve} from "node:path";
import {setTimeout as delay} from "node:timers/promises";
import test from "node:test";

const moduleUrl=new URL("./native_zoom.mjs",import.meta.url).href;
function processes(){
  return execFileSync("ps",["-axo","pid=,ppid=,command="],{encoding:"utf8"}).trim().split("\n").map(line=>{
    const match=/^\s*(\d+)\s+(\d+)\s+(.*)$/.exec(line);
    return {pid:Number(match[1]),parent:Number(match[2]),command:match[3]};
  });
}
function alive(pid){try{process.kill(pid,0);return true;}catch{return false;}}

test("deadline termination reaps Chromium and erases its owned authenticated profile",{timeout:20000},async()=>{
  const runtime=mkdtempSync(join(tmpdir(),"verboflex-p7-lifecycle-test-"));
  const ready=join(runtime,"ready");
  const script=`import {openNativeZoomBrowser} from ${JSON.stringify(moduleUrl)};import{writeFileSync}from"node:fs";const browser=await openNativeZoomBrowser({runtimeDir:${JSON.stringify(runtime)}});await browser.context.addCookies([{name:"test-session",value:"synthetic-cookie",url:"http://127.0.0.1",httpOnly:true}]);writeFileSync(${JSON.stringify(ready)},"ready");setInterval(()=>{},1000);`;
  const child=spawn(process.execPath,["--input-type=module","-e",script],{stdio:"ignore",detached:true});
  const exit=new Promise(resolve=>child.once("exit",(code,signal)=>resolve({code,signal})));
  let descendants=[],profileRoot;
  try{
    for(let n=0;n<200&&!existsSync(ready);n++){assert.equal(child.exitCode,null,"browser child ended before ready");await delay(25);}
    assert.ok(existsSync(ready),"real Chromium must start before timeout");
    const rows=processes(),owned=new Set([child.pid]);
    for(let pass=0;pass<10;pass++)for(const row of rows)if(owned.has(row.parent))owned.add(row.pid);
    descendants=rows.filter(row=>owned.has(row.pid)&&row.pid!==child.pid);
    const browserRow=descendants.find(row=>row.command.includes("--user-data-dir="));
    assert.ok(browserRow,"real persistent Chromium process required");
    const profile=/--user-data-dir=([^\s]+)/.exec(browserRow.command)[1];
    profileRoot=dirname(profile);
    const nested=resolve(profileRoot).startsWith(realpathSync(runtime)+"/");
    const timeout=setTimeout(()=>process.kill(-child.pid,"SIGTERM"),50);
    const result=await Promise.race([exit,delay(5000,null,{ref:false})]);clearTimeout(timeout);
    const remaining=descendants.filter(row=>alive(row.pid));
    assert.deepEqual(result,{code:143,signal:null},"SIGTERM must await cleanup then exit, without forced kill");
    assert.equal(nested,true,"profile must be inside the caller-owned smoke runtime");
    assert.equal(remaining.length,0,"all owned Chromium processes must be reaped");
    assert.equal(existsSync(profileRoot),false,"cookie-bearing profile must be removed");
    assert.deepEqual(readdirSync(runtime),["ready"]);
  }finally{
    if(child.exitCode===null){try{process.kill(-child.pid,"SIGKILL");}catch{}await exit;}
    for(const row of descendants)if(alive(row.pid)){try{process.kill(row.pid,"SIGKILL");}catch{}}
    if(profileRoot && /^verboflex-p7-browser-/.test(profileRoot.split("/").at(-1)))rmSync(profileRoot,{recursive:true,force:true});
    rmSync(runtime,{recursive:true,force:true});
  }
});
