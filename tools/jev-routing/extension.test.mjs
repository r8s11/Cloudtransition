import { test } from 'node:test';
import assert from 'node:assert/strict';
import { makeExtension } from './extension.mjs';

async function until(f){const end=Date.now()+2000;while(!f()){if(Date.now()>end)throw Error('expected state did not arrive');await new Promise(r=>setTimeout(r,5));}}
function rig({runHelper,fetcher,log,skillsList}={}){
 const handlers={},commands={},messages=[],records=[],sent=[],order=[];let calls=0;
 const pi={on:(e,h)=>handlers[e]=h,registerCommand:(n,h)=>commands[n]=h,sendMessage:m=>{messages.push(m.content);order.push('skillmsg');},sendUserMessage:t=>{sent.push(t);order.push('user');}};
 const ctx={hasUI:true,cwd:process.cwd(),agent:{kind:'main',id:'session'},models:{list:()=>[{provider:'openai-codex',id:'gpt-test',name:'test'}]},ui:{setStatus(){},confirm:async()=>true,input:async()=>'.1'}};
 const transport=async(_url,req)=>{
  calls++;const data=JSON.parse(req.body);const answers={};
  for(const [id,q]of Object.entries(data.questions)){
   const names=Object.keys(q.criteria);const chosen=names.includes('easy')?'easy':names.includes('openai-codex/gpt-test')?'openai-codex/gpt-test':'__none__';answers[id]={type:'choice',choice:chosen};
  }
  return {ok:true,json:async()=>({model:'jev-1.14.0',usage:{input_tokens:100},answers})};
 };
 makeExtension({getKey:async()=> 'test-only-key',discoverSkills:async()=>skillsList||[],fetcher:fetcher||transport,log:log||{append:async r=>records.push(r)},runHelper:runHelper||(async({task})=>({reply:'Answer to '+task,cost:.001}))})(pi);
 return {pi,ctx,handlers,commands,messages,records,sent,order,get calls(){return calls;}};
}
test('off is inert; on routes each message once and off cancels pending work',async()=>{
 let release;const gate=new Promise(r=>release=r);let tasks=[];
 const r=rig({runHelper:async({task})=>{tasks.push(task);await gate;return {reply:task,cost:0};}});
 assert.equal(r.handlers.input({text:'normal'},r.ctx),undefined);assert.equal(r.calls,0);
 await r.commands.jev.handler('on',r.ctx);
 assert.deepEqual(r.handlers.input({text:'one'},r.ctx),{handled:true});
 r.handlers.input({text:'two'},r.ctx);
 await until(()=>tasks.length===1);
 await r.commands.jev.handler('off',r.ctx);release();await until(()=>r.messages.some(m=>m.includes('cancelled before dispatch')));
 assert.deepEqual(tasks,['one']);assert.equal(r.records.filter(x=>x.outcome==='picked').length,1);
});
test('successive submissions are classified individually, correlate answers and log picks',async()=>{
 const r=rig();await r.commands.jev.handler('on',r.ctx);
 r.handlers.input({text:'first'},r.ctx);r.handlers.input({text:'second'},r.ctx);
 await until(()=>r.records.filter(x=>x.outcome==='success').length===2);
 const picks=r.records.filter(x=>x.outcome==='picked');assert.equal(new Set(picks.map(x=>x.id)).size,2);
 assert.ok(r.messages.includes('Answer to first')&&r.messages.includes('Answer to second'));
 assert.equal(r.calls,4);
});
test('a provider error is visible, logged, never converted to an arbitrary helper',async()=>{
 let runs=0;const r=rig({fetcher:async()=>{throw Error('secret upstream body');},runHelper:async()=>{runs++;}});
 await r.commands.jev.handler('on',r.ctx);r.handlers.input({text:'hello'},r.ctx);
 await until(()=>r.records.some(x=>x.outcome==='error'));
 assert.equal(runs,0);assert.ok(r.messages.some(x=>x.includes('failed')));assert.ok(!r.messages.join().includes('secret upstream'));
});
test('None in skill-only mode adds no skill body; resubmission bypasses interception',async()=>{
 const r=rig();await r.commands.jev.handler('skills on',r.ctx);r.handlers.input({text:'hello'},r.ctx);
 await until(()=>r.sent.length===1);assert.equal(r.sent[0],'hello');assert.ok(r.messages.some(x=>x.includes('no optional skill')));
});
test('logging failure refuses dispatch rather than silently losing picks',async()=>{
 let runs=0;const r=rig({log:{append:async()=>{throw Error('disk full');}},runHelper:async()=>{runs++;}});
 await r.commands.jev.handler('on',r.ctx);r.handlers.input({text:'hello'},r.ctx);
 await until(()=>r.messages.some(x=>x.includes('logging failure')));assert.equal(runs,0);assert.equal(r.calls,0);
});
test('headless enable and secret-like task do not send requests',async()=>{
 const r=rig();r.ctx.hasUI=false;await r.commands.jev.handler('on',r.ctx);assert.equal(r.handlers.input({text:'hello'},r.ctx),undefined);
 r.ctx.hasUI=true;await r.commands.jev.handler('on',r.ctx);r.handlers.input({text:'api_key=sk-1234567890abcdef'},r.ctx);
 await until(()=>r.records.some(x=>x.outcome==='error'));assert.equal(r.calls,0);
});
test('an unavailable model family is reported and not offered',async()=>{
 const r=rig();await r.commands.jev.handler('on',r.ctx);
 assert.ok(r.messages.some(x=>x.includes('Anthropic helper models unavailable')));
});
test('missing TypeSafe key leaves routing off and sends nothing',async()=>{
 const handlers={},commands={},messages=[];let calls=0;
 const pi={on:(e,h)=>handlers[e]=h,registerCommand:(n,h)=>commands[n]=h,sendMessage:m=>messages.push(m.content),sendUserMessage(){}};
 const ctx={hasUI:true,cwd:process.cwd(),models:{list:()=>[{provider:'anthropic',id:'x'}]},ui:{setStatus(){},confirm:async()=>true,input:async()=>'.1'}};
 makeExtension({getKey:async()=>{throw Error('no key');},fetcher:async()=>{calls++;},log:{append:async()=>{}}})(pi);
 await commands.jev.handler('on',ctx);assert.equal(handlers.input({text:'hello'},ctx),undefined);assert.equal(calls,0);assert.ok(messages.some(x=>x.includes('remains off')));
});
test('a failing helper is reported and logged and no other model is tried',async()=>{
 let runs=0;const r=rig({runHelper:async()=>{runs++;throw Error('Exact helper model unavailable; fallback refused');}});
 await r.commands.jev.handler('on',r.ctx);r.handlers.input({text:'hello'},r.ctx);
 await until(()=>r.records.some(x=>x.outcome==='error'));
 assert.equal(runs,1);assert.equal(r.records.find(x=>x.outcome==='error').errorCode,'Exact helper model unavailable; fallback refused');
 assert.ok(r.messages.some(x=>x.includes('No fallback model was used')));
});
test('a chosen skill body is injected before the original message is released to the main agent',async()=>{
 const {mkdtemp,writeFile}=await import('node:fs/promises');const {tmpdir}=await import('node:os');const {join}=await import('node:path');
 const dir=await mkdtemp(join(tmpdir(),'jev-skill-'));const file=join(dir,'SKILL.md');
 await writeFile(file,'---\nname: research\ndescription: Investigate sources\n---\nRESEARCH BODY');
 const fetcher=async(_u,req)=>{const d=JSON.parse(req.body);const answers={};for(const [id,q] of Object.entries(d.questions))answers[id]={type:'choice',choice:Object.keys(q.criteria).includes('research')?'research':'__none__'};return {ok:true,json:async()=>({model:'jev-1.14.0',usage:{input_tokens:10},answers})};};
 const r=rig({fetcher,skillsList:[{name:'research',description:'Investigate sources',filePath:file}]});
 await r.commands.jev.handler('skills on',r.ctx);r.handlers.input({text:'please research this'},r.ctx);
 await until(()=>r.sent.length===1);
 assert.deepEqual(r.order.slice(-2),['skillmsg','user']);assert.ok(r.messages.some(m=>m.includes('RESEARCH BODY')));assert.equal(r.sent[0],'please research this');
 assert.equal(r.records.find(x=>x.outcome==='skill').skill,'research');
});
