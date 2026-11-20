import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { routeApproved, catalogueHash, taskHash, promptHook } from './agents.mjs';

async function fixture(run) {
 const dir=await mkdtemp(join(tmpdir(),'jev-agents-'));
 try {
  const filePath=join(dir,'SKILL.md'), policyPath=join(dir,'approval.json');
  await writeFile(filePath,'---\nname: research\ndescription: Research sources\n---\nRESEARCH BODY');
  const skills=[{name:'research',description:'Research sources',filePath}];
  const policy={approved:true,runtimes:['claude','codex','gemini','pi','opencode'],expires:new Date(Date.now()+60000).toISOString(),taskHashes:[taskHash('Research tides')],catalogueHash:catalogueHash(skills),maxUSD:0.01};
  await writeFile(policyPath,JSON.stringify(policy));
  let calls=0;
  const fetcher=async()=>{calls++;return {ok:true,json:async()=>({model:'jev-1.14.0',usage:{input_tokens:10},answers:{group_0:{type:'choice',choice:'research'}}})};};
  await run({dir,skills,policy,policyPath,fetcher,calls:()=>calls});
 } finally { await rm(dir,{recursive:true,force:true}); }
}
test('prompt hooks load the chosen body only after a valid classifier answer',()=>fixture(async f=>{
 for(const runtime of ['claude','codex','gemini']) {
  const out=await promptHook(runtime,{hook_event_name:runtime==='gemini'?'BeforeAgent':'UserPromptSubmit',session_id:'local-fixture',prompt:'Research tides',cwd:f.dir},{...f,getKey:async()=> 'fixture-key'});
  assert.match(out.hookSpecificOutput.additionalContext,/RESEARCH BODY/);
  assert.match(out.hookSpecificOutput.additionalContext,/Required skills and higher-priority instructions remain binding/);
 }
 assert.equal(f.calls(),3);
 const raw=await readFile(f.policyPath+'.picks.jsonl','utf8');
 assert.ok(!raw.includes('Research tides')&&!raw.includes('fixture-key'));
}));
test('unapproved task or changed catalogue fails closed without a request',()=>fixture(async f=>{
 await assert.rejects(routeApproved({runtime:'claude',session:'x',task:'Unapproved text',...f}),/not authorized/);
 await assert.rejects(routeApproved({runtime:'claude',session:'x',task:'Research tides',...f,skills:[]}),/catalogue/);
 assert.equal(f.calls(),0);
}));
test('spent budget persists across hook processes and failures keep the reservation',()=>fixture(async f=>{
 // Cap fits one 64k-token reservation (~0.002688) but not two; the exact literal loses to float rounding.
 await writeFile(f.policyPath,JSON.stringify({...f.policy,maxUSD:0.003}));
 await assert.rejects(routeApproved({runtime:'codex',session:'x',task:'Research tides',...f,getKey:async()=> 'fixture-key',fetcher:async()=>{throw Error('private upstream error');}}),/Jev request failed/);
 await assert.rejects(routeApproved({runtime:'codex',session:'x',task:'Research tides',...f,getKey:async()=> 'fixture-key'}),/budget exhausted/);
 assert.equal(f.calls(),0);
}));
test('disabled hook preserves native workflow and discloses disabled routing',async()=>{
 const out=await promptHook('codex',{hook_event_name:'UserPromptSubmit',prompt:'ordinary',session_id:'x'},{policyPath:''});
 assert.match(out.hookSpecificOutput.additionalContext,/routing off/);
});
test('provider failure never becomes None or a skill load',()=>fixture(async f=>{
 const out=await promptHook('claude',{hook_event_name:'UserPromptSubmit',session_id:'x',prompt:'Research tides',cwd:f.dir},{...f,getKey:async()=> 'fixture-key',fetcher:async()=>{throw Error('upstream private content');}});
 assert.equal(out.decision,'block');assert.ok(!JSON.stringify(out).includes('upstream private content'));assert.equal(out.hookSpecificOutput,undefined);
}));
test('OpenCode V2 uses the native location/data catalogue envelope',()=>fixture(async f=>{
 const {setupOpenCode}=await import('./opencode.mjs');
 let prompt,disposed=false;
 const ctx={skill:{list:async()=>({location:{directory:f.dir},data:f.skills.map(s=>({id:s.name,name:s.name,description:s.description,path:s.filePath,content:'RESEARCH BODY'}))})},session:{hook:async(name,handler)=>{assert.equal(name,'prompt');prompt=handler;return {dispose:async()=>{disposed=true;}};}}};
 const cleanup=await setupOpenCode(ctx,{...f,getKey:async()=> 'fixture-key'});
 const event={sessionID:'fixture',prompt:{text:'Research tides'}};
 await prompt(event);assert.match(event.prompt.text,/RESEARCH BODY/);
 assert.equal(f.calls(),1);await cleanup();assert.equal(disposed,true);
}));
test('OpenCode preserves duplicate display names using stable native IDs and embedded bodies',()=>fixture(async f=>{
 const {setupOpenCode}=await import('./opencode.mjs');
 const native=[{id:'research',name:'Shared display name',description:'Research sources',path:'skill://research/SKILL.md',content:'EMBEDDED BODY'},{id:'browser',name:'Shared display name',description:'Browse pages',path:'skill://browser/SKILL.md',content:'BROWSER BODY'}];
 const skills=native.map(s=>({name:s.id,description:s.name+': '+s.description,filePath:s.path}));
 await writeFile(f.policyPath,JSON.stringify({...f.policy,catalogueHash:catalogueHash(skills)}));
 let prompt;const ctx={skill:{list:async()=>({data:native})},session:{hook:async(_name,handler)=>{prompt=handler;return {dispose:async()=>{}};}}};
 await setupOpenCode(ctx,{policyPath:f.policyPath,fetcher:f.fetcher,getKey:async()=> 'fixture-key'});
 const event={sessionID:'fixture',prompt:{text:'Research tides'}};await prompt(event);
 assert.match(event.prompt.text,/EMBEDDED BODY/);assert.ok(!event.prompt.text.includes('BROWSER BODY'));
 assert.equal(f.calls(),1);
}));
test('approval accounting refuses symlink writes before a provider request',()=>fixture(async f=>{
 const {symlink}=await import('node:fs/promises');
 const target=join(f.dir,'protected.json'),original=JSON.stringify({spent:0,tokens:0,calls:0});
 await writeFile(target,original);await symlink(target,f.policyPath+'.usage.json');
 await assert.rejects(routeApproved({runtime:'claude',session:'fixture',task:'Research tides',...f,getKey:async()=> 'fixture-key'}));
 assert.equal(f.calls(),0);assert.equal(await readFile(target,'utf8'),original);
}));
test('persisted usage cannot override the approved cap with extra client fields',()=>fixture(async f=>{
 await writeFile(f.policyPath,JSON.stringify({...f.policy,maxUSD:0.002688}));
 await writeFile(f.policyPath+'.usage.json',JSON.stringify({spent:0.002688,tokens:0,calls:1,budget:100}));
 await assert.rejects(routeApproved({runtime:'claude',session:'fixture',task:'Research tides',...f,getKey:async()=> 'fixture-key'}),/budget exhausted/);
 assert.equal(f.calls(),0);
}));
