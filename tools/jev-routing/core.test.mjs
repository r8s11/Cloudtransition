import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { JevClient, choose, PickLog, loadSkill, eligibleModels } from './core.mjs';

const skills = n => Array.from({length:n}, (_,i)=>({name:`skill-${i}`,description:`Specific capability ${i}`}));
const client = choice => ({ask: async questions => Object.fromEntries(Object.entries(questions).map(([id,q])=>[id,{type:'choice',choice:choice(q),probabilities:{}}]))});

test('None loads no skill and a chosen skill must belong to its group', async()=>{
 assert.equal(await choose(client(()=> '__none__'),'task',skills(2)),null);
 await assert.rejects(choose(client(()=> 'invented'),'task',skills(2)),/unknown choice/i);
});
test('large catalogues include every candidate and arbitrate winners without comparing group probabilities',async()=>{
 const seen=[],calls=[];
 const c=client(q=>{const names=Object.keys(q.criteria);calls.push(names);seen.push(...names);return names.includes('skill-299')?'skill-299':names[0];});
 assert.equal(await choose(c,'task',skills(300)),'skill-299');
 assert.equal(new Set(seen.filter(x=>x!=='__none__')).size,300);
 assert.ok(calls.every(x=>x.length<=255 && x.includes('__none__')));
 assert.equal(calls.at(-1).length,3);
});
test('no consent, no budget and secret-like input make zero network requests',async()=>{
 let count=0; const fetcher=async()=>{count++;throw Error('unexpected');};
 for(const config of [{consent:false,budget:1},{consent:true,budget:0}]){
  const c=new JevClient({...config,key:'secret',fetcher});await assert.rejects(c.ask({q:{type:'choice',criteria:{a:'A'}}},{task:'hello'}));
 }
 const c=new JevClient({consent:true,budget:1,key:'secret',fetcher});
 await assert.rejects(c.ask({q:{type:'choice',criteria:{a:'A'}}},{task:'api_key=sk-abcdefghijk123456789'}),/secret/i);
 assert.equal(count,0);
});
test('network failure reserves the worst-case charge and never becomes None',async()=>{
 const c=new JevClient({consent:true,budget:.003,key:'secret',fetcher:async()=>{throw Error('private error body');}});
 await assert.rejects(choose(c,'hello',skills(1)),/request failed/i);
 assert.ok(c.spent>0);await assert.rejects(choose(c,'hello',skills(1)),/budget/i);
});
test('response must match the pinned model and contain requested answers',async()=>{
 const c=new JevClient({consent:true,budget:1,key:'secret',fetcher:async()=>({ok:true,json:async()=>({model:'wrong',answers:{},usage:{input_tokens:1}})})});
 await assert.rejects(choose(c,'hello',skills(1)),/model/i);
});
test('pick log excludes message bodies and secret fields and has private permissions',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'jev-log-'));const p=join(dir,'logs','picks.jsonl');
 const l=new PickLog(p);await l.append({id:'one',outcome:'picked',skill:'research',task:'PRIVATE CANARY',key:'SECRET'});
 const s=await readFile(p,'utf8');assert.ok(!s.includes('CANARY')&&!s.includes('SECRET'));assert.equal((await stat(p)).mode&0o777,0o600);
});
test('skill loading rejects changes and unknown paths rather than loading arbitrary files',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'jev-skill-'));const p=join(dir,'SKILL.md');await writeFile(p,'---\nname: useful\ndescription: Useful thing\n---\nDo useful work.');
 const ss=[{name:'useful',description:'Useful thing',filePath:p}];assert.match(await loadSkill('useful',ss),/Do useful work/);
 await assert.rejects(loadSkill('missing',ss),/unknown/i);
 await writeFile(p,'---\nname: other\ndescription: Changed\n---\nChanged');await assert.rejects(loadSkill('useful',ss),/changed/i);
});
test('model candidates include both companies and exclude other providers',()=>{
 const m=eligibleModels([{provider:'anthropic',id:'claude-haiku-5'},{provider:'openai-codex',id:'gpt-6.1'},{provider:'google',id:'gemini'}]);
 assert.deepEqual(m.map(x=>x.name),['anthropic/claude-haiku-5','openai-codex/gpt-6.1']);
});
test('a rejected API request is an error, never None or an invented answer',async()=>{
 const c=new JevClient({consent:true,budget:1,key:'secret',fetcher:async()=>({ok:false,status:401,json:async()=>({detail:'private body'})})});
 await assert.rejects(choose(c,'hello',skills(1)),/Jev HTTP 401/);
});
