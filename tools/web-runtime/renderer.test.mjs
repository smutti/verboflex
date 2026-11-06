import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {capture} from './renderer.mjs';

async function render(html, scenario={}) {
 const directory=await mkdtemp(join(tmpdir(),'web-render-test-'));
 try{
  await writeFile(join(directory,'index.html'),html);
  return await capture({directory,scenario:{route:'#/',ready:'body',actions:[],responses:[],target:'#target',...scenario},language:'en',catalogs:{},viewport:{width:390,height:844},output:join(directory,'image.png'),timeout:1200});
 }finally{await rm(directory,{recursive:true,force:true});}
}
const target='<div id="target">Synthetic message</div>';
test('fresh contexts do not retain session state',async()=>{
 const html=`${target}<script>if(localStorage.getItem('dirty'))throw Error('stale');localStorage.setItem('dirty','1');</script>`;
 assert.equal((await render(html)).text,'Synthetic message');
 assert.equal((await render(html)).text,'Synthetic message');
});
for(const [label,html] of [
 ['external request',target+'<script>fetch("https://example.test/private")</script>'],
 ['unregistered API',target+'<script>fetch("/api/unregistered")</script>'],
 ['socket',target+'<script>new WebSocket("ws://example.test/socket")</script>'],
 ['page error',target+'<script>throw Error("synthetic")</script>'],
 ['ambiguous target',target+target],
 ['clipped target','<div style="height:10px;overflow:hidden"><div id="target" style="height:100px">Clipped</div></div>'],
 ['raw parameter','<div id="target">Unresolved {{value.requiredLength}}</div>'],
 ['missing target','<div>No target</div>'],
])test(`rejects ${label}`,async()=>{await assert.rejects(render(html));});
test('API fixture query strings match exactly',async()=>{
 await assert.rejects(render(target+'<script>fetch("/api/sites?live=1")</script>',{responses:[{path:'/api/sites',method:'GET',body:[]}]}));
});
test('fixed dialog portals are not clipped by a short scroll-locked body',async()=>{
 const result=await render('<body style="overflow:hidden;height:10px"><section style="position:fixed;top:50px;left:10px"><h2 id="target">Modal title</h2></section></body>');
 assert.equal(result.text,'Modal title');
});
test('placeholder evidence requires an empty visible input',async()=>{
 assert.equal((await render('<input id="target" placeholder="Search sites">',{target_attribute:'placeholder'})).text,'Search sites');
 await assert.rejects(render('<input id="target" placeholder="Search sites" value="Content">',{target_attribute:'placeholder'}));
});
