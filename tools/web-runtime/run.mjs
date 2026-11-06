/** Trusted entry point inside the offline build/browser container. */
import { readFile, writeFile, mkdir, symlink, realpath } from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { capture } from './renderer.mjs';
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const inputBytes = await readFile('/input.json');
if(inputBytes.length > 4*1024*1024)throw Error('Input too large');
const input = JSON.parse(inputBytes);
const profile = JSON.parse(await readFile('/opt/web-profile.json','utf8'));
if(input.engine!=='web'||input.version!==2||!/^[a-f0-9]{40,64}$/.test(input.commit)||input.capture.runner_profile!==profile.name)throw Error('Invalid bundle');
const directory = '/tmp/application';
await mkdir(directory);
// The worker supplied a commit-bound archive. No .git config or credentials enter this container.
execFileSync('tar',['-xf','/source.tar','-C',directory]);
for(const source of input.sources){
 const path=await realpath(resolve(directory,source.path));
 if(!path.startsWith(directory+'/')||digest(await readFile(path))!==source.sha256)throw Error('Imported source does not match the prepared revision');
}
const root=resolve(directory,input.capture.application_root??'.');
if(root!==directory&&!root.startsWith(directory+'/'))throw Error('Invalid root');
if(digest(await readFile(root+'/package-lock.json'))!==profile.lockfile_sha256)throw Error('Dependencies are not prepared for this revision');
await symlink('/opt/application-dependencies/node_modules',root+'/node_modules');
execFileSync('/opt/node20/bin/node',profile.build_args,{cwd:root,stdio:'ignore',timeout:600000,env:{PATH:'/opt/node20/bin:/usr/bin:/bin',HOME:'/tmp',NG_CLI_ANALYTICS:'false'}});
const dist=resolve(root,profile.dist);
if(!dist.startsWith(root+'/'))throw Error('Invalid build output');
const scenario={...input.scenario,target:input.scenario.targets[0].selector,target_attribute:input.scenario.targets[0].attribute};
if(input.scenario.targets.length!==1)throw Error('Exact target required');
const observation=await capture({directory:dist,scenario,language:input.language,catalogs:input.catalogs,viewport:input.viewport,output:'/tmp/capture.png'});
const png=await readFile('/tmp/capture.png');
if(png.length>8*1024*1024)throw Error('Image too large');
const receipt={engine:'web',version:1,render_id:randomUUID(),rendered_at:new Date().toISOString(),input_digest:digest(inputBytes),image_digest:digest(png),commit:input.commit,scenario_id:input.request.scenario_id,language:input.language,viewport:input.request.viewport,manifest_digest:input.manifest_digest,source_digest:input.source_digest,location:{status:'found',regions:observation.regions},text:observation.text};
process.stdout.write(JSON.stringify({png:png.toString('base64'),receipt}));
