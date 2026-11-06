import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {capture} from './renderer.mjs';
const root=resolve(import.meta.dirname,'../fixtures/angular-web');
const output=resolve(process.argv[2]||'/tmp/verboflex-web-capture-p0');
await mkdir(output,{recursive:true});
const manifest=JSON.parse(await readFile(root+'/capture.json','utf8'));
const receipt=[];
for(const language of ['en','it'])for(const [profile,viewport] of Object.entries({desktop:{width:1440,height:900},mobile:{width:390,height:844}}))for(const scenario of manifest.scenarios){
  const target=scenario.targets[0];
  const data=JSON.parse(await readFile(root+`/src/assets/i18n/${language}.json`,'utf8'));
  const [parent,key]=target.key.split('.');
  data[parent][key]=scenario.id==='tenant.create.validation'?`Saved ${language}: {{ value.requiredLength }} characters`:`Saved ${language}: ${target.key}`;
  const result=await capture({directory:root+'/dist/browser',scenario:{...scenario,target:target.selector},language,catalogs:{[`/assets/i18n/${language}.json`]:data},viewport,output:`${output}/${scenario.id}-${language}-${profile}.png`});
  assert.equal(result.text,scenario.id==='tenant.create.validation'?`Saved ${language}: 97 characters`:`Saved ${language}: ${target.key}`);
  assert.deepEqual(result.violations,[]);
  receipt.push({scenario:scenario.id,language,profile,...result});
  console.log(`PASS ${scenario.id} ${language} ${profile}`);
}
await writeFile(output+'/receipt.json',JSON.stringify(receipt,null,2));
console.log(`${receipt.length} real Angular/Chromium renders passed`);
