import http from 'node:http';
import { spawn } from 'node:child_process';
import readline from 'node:readline';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const wire=[],frames=[];let toolAsked=false,helperRequests=0,toolResultSeen=null,helperSystem='';
const server=http.createServer(async(req,res)=>{
 let body='';for await(const part of req)body+=part;const data=JSON.parse(body||'{}');
 wire.push({path:req.url,model:data.model});
 const toolMsg=(data.messages||[]).filter(m=>m.role==='tool').at(-1);if(toolMsg)toolResultSeen=String(typeof toolMsg.content==='string'?toolMsg.content:JSON.stringify(toolMsg.content)).slice(0,160);
 const sysAll=(data.messages||[]).filter(m=>m.role==='system'||m.role==='developer').map(m=>typeof m.content==='string'?m.content:JSON.stringify(m.content)).join('\n');if(req.url!=='/classify')helperSystem=sysAll||JSON.stringify((data.messages||[]).map(m=>m.role));
 if(req.url==='/classify'){
  const answers={};for(const [id,q]of Object.entries(data.questions)){
   const names=Object.keys(q.criteria);answers[id]={type:'choice',choice:names.includes('medium')?'medium':names.includes('openai/jev-fixture')?'openai/jev-fixture':'__none__'};
  }
  res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({model:'jev-1.14.0',answers,usage:{input_tokens:100}}));return;
 }
 helperRequests++;res.writeHead(200,{'Content-Type':'text/event-stream'});
 const chunk=delta=>res.write('data: '+JSON.stringify({id:'test',object:'chat.completion.chunk',created:1,model:'jev-fixture',choices:[{index:0,delta,finish_reason:null}]})+'\n\n');
 if(helperRequests===1){
  chunk({role:'assistant',tool_calls:[{index:0,id:'read-one',type:'function',function:{name:'read',arguments:JSON.stringify({path:'tools/jev-routing/core.mjs'})}}]});
 }else chunk({role:'assistant',content:'LOCAL HELPER ANSWER'});
 res.write('data: '+JSON.stringify({id:'test',object:'chat.completion.chunk',created:1,model:'jev-fixture',choices:[{index:0,delta:{},finish_reason:helperRequests===1?'tool_calls':'stop'}],usage:{prompt_tokens:10,completion_tokens:5,total_tokens:15}})+'\n\n');
 res.end('data: [DONE]\n\n');
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const home=await mkdtemp(join(tmpdir(),'jev-runtime-'));
const logPath=join(home,'picks.jsonl');
const child=spawn('omp',['--mode','rpc','--no-extensions','-e',fileURLToPath(new URL('./runtime-fixture.mjs',import.meta.url)),'--no-session','--no-title','--no-lsp','--no-context-files'],{cwd:process.cwd(),env:{...process.env,OPENAI_API_KEY:'fixture-local-only',ANTHROPIC_API_KEY:'fixture-local-only',JEV_SMOKE_LOG:logPath,JEV_SMOKE_ORIGIN:`http://127.0.0.1:${server.address().port}`},stdio:['pipe','pipe','pipe']});
let stderr='';child.stderr.on('data',b=>stderr+=b);
const pending=new Map();let seq=0;
const send=message=>child.stdin.write(JSON.stringify(message)+'\n');
const prompt=message=>new Promise((resolve,reject)=>{const id='p'+(++seq);pending.set(id,{resolve,reject});send({id,type:'prompt',message});});
let readyResolve;const ready=new Promise(r=>readyResolve=r);
const line=readline.createInterface({input:child.stdout});
line.on('line',s=>{
 let e;try{e=JSON.parse(s);}catch{return;}frames.push(e);
 if(e.type==='extension_ui_request'&&['input','confirm','select','editor'].includes(e.method))console.log('UI',e.method,e.title);
 if(e.type==='message_end')console.log('MESSAGE',JSON.stringify(e.message?.content).slice(0,500));
 if(e.type==='response')console.log('RESPONSE',e.id,e.success);
 if(e.type==='ready')readyResolve();
 if(e.type==='extension_ui_request'){
  if(e.method==='input')send({type:'extension_ui_response',id:e.id,value:'0.1'});
  if(e.method==='select')send({type:'extension_ui_response',id:e.id,cancelled:true});
  if(e.method==='editor')send({type:'extension_ui_response',id:e.id,cancelled:true});
  if(e.method==='confirm'){
   const tool=e.title?.includes('tool approval');if(tool)toolAsked=true;
   send({type:'extension_ui_response',id:e.id,confirmed:!tool});
  }
 }
 if(e.type==='response'&&pending.has(e.id)){const p=pending.get(e.id);pending.delete(e.id);e.success?p.resolve(e):p.reject(Error(e.error));}
});
const deadline=setTimeout(()=>{console.error('TIMEOUT',JSON.stringify({wire,stderr:stderr.slice(-800),pending:[...pending.keys()]}));child.kill('SIGKILL');for(const p of pending.values())p.reject(Error('RPC timeout'));readyResolve();},45000);
async function waitFor(predicate){const end=Date.now()+30000;while(!predicate()){if(child.exitCode!==null)throw Error('Omp exited: '+stderr.slice(-1000));if(Date.now()>end){let picks='';try{picks=await readFile(logPath,'utf8');}catch{}throw Error('Runtime evidence: '+JSON.stringify({picks:picks.split('\n').filter(Boolean).map(l=>JSON.parse(l).errorCode||JSON.parse(l).outcome),wire,toolResultSeen,helperErr:(stderr.match(/HELPER_ERROR[\s\S]{0,1200}/)||[''])[0]}));}await new Promise(r=>setTimeout(r,20));}}
try{
 await ready;await prompt('/jev status');await prompt('/jev on');await waitFor(()=>frames.some(e=>e.type==='message_end'&&e.message?.content==='Jev on. Restart/new/switch resets it to off.'));await prompt('Describe the local smoke test.');
 await waitFor(()=>frames.some(e=>e.type==='message_end'&&e.message?.content==='LOCAL HELPER ANSWER'));
 await prompt('/jev off');const n=wire.length;await prompt('/jev status');assert.equal(wire.length,n);
 const logs=(await readFile(logPath,'utf8')).trim().split('\n').map(JSON.parse);
 console.log('DIAG',JSON.stringify({helperRequests,toolResult:toolResultSeen,systemHasParentPolicy:helperSystem.includes('Parent session instructions (remain binding)')}));assert.ok(helperSystem.includes('Parent session instructions (remain binding)'),'helper must receive parent instructions');assert.ok(toolAsked,'helper tool approval must reach parent');assert.ok(/declined|blocked/i.test(toolResultSeen||'')&&!toolResultSeen.includes('import { readFile'),'denied tool must be blocked');assert.equal(logs.filter(x=>x.outcome==='picked').length,1);assert.equal(logs.filter(x=>x.outcome==='success').length,1);
 assert.ok(wire.findIndex(x=>x.path==='/classify')<wire.findIndex(x=>x.path!=='/classify'));
 console.log(JSON.stringify({result:'pass',classifierCalls:wire.filter(x=>x.path==='/classify').length,helperRequests,toolApprovalDenied:toolAsked,logOutcomes:logs.map(x=>x.outcome),errors:frames.filter(x=>x.type==='extension_error')},null,2));
}finally{clearTimeout(deadline);child.kill();line.close();server.closeAllConnections();server.close();}
