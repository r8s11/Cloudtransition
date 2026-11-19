// Narrow acceptance experiment: real Omp RPC + SDK helpers, localhost providers only.
// U2 exercises easy/medium/hard with both families; R2 observes required skill reads.
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { startServer, startOmp, sse, textOfContent } from './harness.mjs';
const work=await mkdtemp(join(tmpdir(),'jev-acceptance-'));
const report={providers:'localhost only; no paid or private-source calls',command:[],skills:[]};
const tasks=[
 {text:'What is two plus two?',difficulty:'easy',model:'anthropic/haiku-fixture'},
 {text:'Fix this pagination helper off-by-one error.',difficulty:'medium',model:'openai-codex/codex-fixture'},
 {text:'Design a consistent multi-region payment ledger.',difficulty:'hard',model:'anthropic/opus-fixture'},
];
let om,srv;
try {
 srv=await startServer(async({event,data,res})=>{
  if(event.path==='/classify') {
   const task=tasks.find(t=>(data.state.task||'').includes(t.text)),answers={};
   for(const[id,q]of Object.entries(data.questions))answers[id]={type:'choice',choice:Object.hasOwn(q.criteria,'easy')?task.difficulty:task.model};
   res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({model:'jev-1.14.0',answers,usage:{input_tokens:10}}));return true;
  }
  sse(res,[{role:'assistant',content:`LOCAL ANSWER ${data.model}`}]);return true;
 });
 const log=join(work,'command.jsonl');
 om=await startOmp({cwd:work,config:{origin:srv.origin,key:'fixture-local-only',providers:{jevmain:['main'],anthropic:['haiku-fixture','opus-fixture'],'openai-codex':['codex-fixture']},log},extraArgs:['--model','jevmain/main']});
 await om.prompt('/jev on');await om.waitFor(()=>om.messages().some(m=>/^Jev on\./.test(m.text)),'enable');
 for(const task of tasks){
  const n=srv.events.length,offset=om.messages().length;
  await om.prompt(task.text);
  await om.waitFor(()=>om.messages().slice(offset).some(m=>m.text===`LOCAL ANSWER ${task.model.split('/')[1]}`),'helper answer');
  const events=srv.events.slice(n),classify=events.filter(e=>e.path==='/classify'),helpers=events.filter(e=>e.path!=='/classify');
  assert.equal(classify.length,2);assert.equal(helpers.length,1);assert.equal(helpers[0].model,task.model.split('/')[1]);assert.ok(classify[1].seq<helpers[0].seq);
  assert.ok(classify[1].respondedAt<=helpers[0].at,'classifier response completed before helper request');
  assert.equal(helpers[0].data.messages.filter(m=>m.role==='user'&&textOfContent(m.content).endsWith(task.text)).length,1);
  report.command.push({difficulty:task.difficulty,model:task.model,ordered:events.map(e=>({sequence:e.seq,requestAt:e.at,responseAt:e.respondedAt,event:e.path==='/classify'?'Jev request/response':'helper request/response'})),helperCalls:1});
 }
 const records=(await readFile(log,'utf8')).trim().split('\n').map(JSON.parse);
 assert.deepEqual(records.filter(r=>r.outcome==='picked').map(r=>[r.difficulty,r.model]),tasks.map(t=>[t.difficulty,t.model]));
 assert.equal(records.filter(r=>r.outcome==='success').length,3);
 assert.ok(tasks.every(t=>!JSON.stringify(records).includes(t.text)));
 report.commandLog=records;
 await om.stop();om=null;srv.close();srv=null;
 for(const selected of ['optional-fixture','__none__']){
  const cwd=join(work,selected);await mkdir(cwd);
  for(const name of ['mandatory-fixture','optional-fixture']){
   const dir=join(cwd,'.omp/skills',name);await mkdir(dir,{recursive:true});
   await writeFile(join(dir,'SKILL.md'),`---\nname: ${name}\ndescription: Local fixture skill ${name}\n---\nBODY-OF-${name}\n`);
  }
  srv=await startServer(async({event,data,res})=>{
   if(event.path==='/classify'){
    const answers=Object.fromEntries(Object.keys(data.questions).map(id=>[id,{type:'choice',choice:selected}]));
    res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({model:'jev-1.14.0',answers,usage:{input_tokens:10}}));return true;
   }
   if(data.messages.at(-1)?.role==='user')sse(res,[{role:'assistant',tool_calls:[{index:0,id:'required-read',type:'function',function:{name:'read',arguments:JSON.stringify({path:'skill://mandatory-fixture'})}}]}],'tool_calls');
   else sse(res,[{role:'assistant',content:'REQUIRED READ COMPLETE'}]);return true;
  });
  om=await startOmp({cwd,config:{origin:srv.origin,key:'fixture-local-only',providers:{jevmain:['main']},skills:'real-project',log:join(work,selected+'.jsonl')},extraArgs:['--model','jevmain/main','--append-system-prompt','SYSTEM REQUIRED: Read skill://mandatory-fixture before answering every task. Jev never suppresses this instruction.']});
  await om.prompt('/jev skills on');await om.waitFor(()=>om.messages().some(m=>/^Jev skills\./.test(m.text)),'skills enabled');
  await om.prompt('Explain ocean tides.');await om.waitFor(()=>om.messages().some(m=>m.text==='REQUIRED READ COMPLETE'),'required skill load');
  const events=srv.events,requests=events.filter(e=>e.path!=='/classify');
  assert.ok(events[0].path==='/classify');assert.equal(requests.length,2);
  assert.ok(events[0].respondedAt<=requests[0].at,'Jev response completed before optional skill injection');
  const first=requests[0].data.messages;
  assert.ok(first.some(m=>['system','developer'].includes(m.role)&&textOfContent(m.content).includes('SYSTEM REQUIRED')));
  const selectedInjected=first.some(m=>textOfContent(m.content).includes('BODY-OF-optional-fixture'));
  assert.equal(selectedInjected,selected!=='__none__');
  const tool=requests[1].data.messages.find(m=>m.role==='tool');assert.ok(textOfContent(tool?.content).includes('BODY-OF-mandatory-fixture'));
  report.skills.push({choice:selected,sequence:events.map(e=>({requestAt:e.at,responseAt:e.respondedAt,sequence:e.seq,event:e.path==='/classify'?'Jev request/response':e===requests[0]?'optional context + binding required instruction':'required skill read result'})),optionalBodyInjected:selectedInjected,requiredBodyRead:true});
  await om.stop();om=null;srv.close();srv=null;
 }
 report.status='observed';console.log(JSON.stringify(report,null,2));
 if(process.argv[2])await writeFile(process.argv[2],JSON.stringify(report,null,2)+'\n');
} finally {if(om)await om.stop();if(srv)srv.close();await rm(work,{recursive:true,force:true});}
