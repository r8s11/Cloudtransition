// Real native runtimes with synthetic tasks and localhost-only Jev/model endpoints.
// Never bypass hook trust, permission dialogs, or provider safety checks.
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { catalogueHash, taskHash } from './agents.mjs';
import { startServer, sse } from './harness.mjs';
const work=await mkdtemp(join(tmpdir(),'jev-native-'));
const hook=fileURLToPath(new URL('./agent-fixture.mjs',import.meta.url));
const task='Research ocean tides using the optional fixture skill.';
const report=[];
const runtimes=process.argv.slice(2).filter(x=>!x.startsWith('--'));
const output=process.argv.slice(2).find(x=>x.startsWith('--output='))?.slice(9);
const disabled=process.argv.includes('--disabled');
const wanted=runtimes.length?runtimes:['claude','codex','pi','opencode'];
const quote=s=>"'"+s.replaceAll("'","'\\''")+"'";
const baseEnv={PATH:process.env.PATH,HOME:process.env.HOME,TMPDIR:process.env.TMPDIR,LANG:'en_US.UTF-8',TERM:'dumb',NO_COLOR:'1',PI_OFFLINE:'1',PI_TELEMETRY:'0',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:'1',DISABLE_AUTOUPDATER:'1'};
async function launch(binary,args,env,cwd){
 return new Promise(resolve=>{
  const child=spawn(binary,args,{cwd,env,stdio:['ignore','pipe','pipe']});let stdout='',stderr='';
  child.stdout.on('data',b=>stdout+=b);child.stderr.on('data',b=>stderr+=b);
  const timer=setTimeout(()=>{child.kill('SIGKILL');},45000);
  child.on('error',error=>{clearTimeout(timer);resolve({exit:null,stdout,stderr:String(error.message)});});
  child.on('close',(exit,signal)=>{clearTimeout(timer);resolve({exit,signal,stdout,stderr});});
 });
}
try{
 for(const runtime of wanted){
  const cwd=runtime==='gemini'&&process.env.JEV_GEMINI_PROFILE?join(process.env.JEV_GEMINI_PROFILE,'workspace'):join(work,runtime);await mkdir(cwd,{recursive:true});
  const filePath=join(cwd,'SKILL.md');await writeFile(filePath,'---\nname: optional-fixture\ndescription: Research ocean tides\n---\nLOCAL-OPTIONAL-BODY-7d2f\n');
  const skills=[{name:'optional-fixture',description:'Research ocean tides',filePath}];
  const policyPath=join(cwd,'approval.json'),cataloguePath=join(cwd,'catalogue.json');
  await writeFile(cataloguePath,JSON.stringify(skills));
  await writeFile(policyPath,JSON.stringify({approved:true,runtimes:[runtime],expires:new Date(Date.now()+120000).toISOString(),taskHashes:[taskHash(task)],catalogueHash:catalogueHash(skills),maxUSD:0.01}));
  const srv=await startServer(async({event,data,res})=>{
   if(event.path==='/classify'){
    const answers=Object.fromEntries(Object.keys(data.questions).map(id=>[id,{type:'choice',choice:'optional-fixture'}]));
    res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({model:'jev-1.14.0',answers,usage:{input_tokens:10}}));return true;
   }
   if(event.path.includes('/messages')){
    res.writeHead(200,{'Content-Type':'text/event-stream'});
    const send=(type,data)=>res.write(`event: ${type}\ndata: ${JSON.stringify({type,...data})}\n\n`);
    send('message_start',{message:{id:'fixture',type:'message',role:'assistant',model:data.model,content:[],stop_reason:null,stop_sequence:null,usage:{input_tokens:10,output_tokens:1}}});
    send('content_block_start',{index:0,content_block:{type:'text',text:''}});send('content_block_delta',{index:0,delta:{type:'text_delta',text:'LOCAL NATIVE ANSWER'}});send('content_block_stop',{index:0});send('message_delta',{delta:{stop_reason:'end_turn',stop_sequence:null},usage:{output_tokens:4}});send('message_stop',{});res.end();return true;
   }
   if(event.path.includes(':streamGenerateContent')){
    res.writeHead(200,{'Content-Type':'text/event-stream'});res.write('data: '+JSON.stringify({candidates:[{content:{role:'model',parts:[{text:'LOCAL NATIVE ANSWER'}]},finishReason:'STOP'}],usageMetadata:{promptTokenCount:10,candidatesTokenCount:4,totalTokenCount:14}})+'\n\n');res.end();return true;
   }
   if(event.path.includes('/responses')){
    const response={id:'resp_fixture',object:'response',created_at:1,status:'completed',model:data.model,output:[{id:'msg_fixture',type:'message',status:'completed',role:'assistant',content:[{type:'output_text',text:'LOCAL NATIVE ANSWER',annotations:[]}]}],usage:{input_tokens:10,output_tokens:4,total_tokens:14}};
    res.writeHead(200,{'Content-Type':'text/event-stream'});
    let sequence=0;const send=(type,value)=>res.write(`event: ${type}\ndata: ${JSON.stringify({type,sequence_number:sequence++,...value})}\n\n`);
    const item=response.output[0],part=item.content[0],where={output_index:0,content_index:0,item_id:item.id};
    send('response.created',{response:{...response,status:'in_progress',output:[]}});
    send('response.output_item.added',{output_index:0,item:{...item,status:'in_progress',content:[]}});
    send('response.content_part.added',{...where,part:{...part,text:''}});
    send('response.output_text.delta',{...where,delta:part.text});
    send('response.output_text.done',{...where,text:part.text});
    send('response.content_part.done',{...where,part});
    send('response.output_item.done',{output_index:0,item});
    send('response.completed',{response});res.end();return true;
   }
   sse(res,[{role:'assistant',content:'LOCAL NATIVE ANSWER'}]);return true;
  });
  try{
   const env={...baseEnv,XDG_CONFIG_HOME:join(cwd,'config'),XDG_DATA_HOME:join(cwd,'data'),XDG_CACHE_HOME:join(cwd,'cache'),XDG_STATE_HOME:join(cwd,'state'),JEV_SKILL_APPROVAL:disabled?'':policyPath,JEV_SKILL_CATALOGUE:cataloguePath,JEV_AGENT_FIXTURE:JSON.stringify({origin:srv.origin}),ANTHROPIC_API_KEY:'fixture-local-only',ANTHROPIC_BASE_URL:srv.origin,OPENAI_API_KEY:'fixture-local-only'};
   const command=`${quote(process.execPath)} ${quote(hook)} ${runtime}`;
   let args;
   if(runtime==='claude'){
    env.CLAUDE_CONFIG_DIR=join(cwd,'claude');
    const settings=join(cwd,'settings.json');await writeFile(settings,JSON.stringify({hooks:{UserPromptSubmit:[{hooks:[{type:'command',command,timeout:60}]}]}}));
    args=['--print','--restricted','--setting-sources','','--settings',settings,'--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--no-session-persistence','--tools','','--model','claude-sonnet-4-5','--output-format','stream-json','--verbose','--include-hook-events',task];
   }else if(runtime==='codex'){
    env.CODEX_HOME=process.env.JEV_CODEX_PROFILE||join(cwd,'codex');await mkdir(env.CODEX_HOME,{recursive:true});
    await writeFile(join(env.CODEX_HOME,'hooks.json'),JSON.stringify({hooks:{UserPromptSubmit:[{hooks:[{type:'command',command,timeout:60}]}]}}));
    const config=`model="fixture"\nmodel_provider="local"\n[model_providers.local]\nname="Local fixture"\nbase_url="http://127.0.0.1:9/v1"\nwire_api="responses"\nrequest_max_retries=0\nstream_max_retries=0\n`;
    await writeFile(join(env.CODEX_HOME,'config.toml'),config,{flag:'wx'}).catch(error=>{if(error.code!=='EEXIST')throw error;});
    args=['exec','--skip-git-repo-check','--ephemeral','--ignore-rules','--sandbox','read-only','--json','-c',`model_providers.local.base_url=${JSON.stringify(srv.origin+'/v1')}`,task];
   }else if(runtime==='pi'){
    env.PI_CODING_AGENT_DIR=join(cwd,'pi');await mkdir(env.PI_CODING_AGENT_DIR);
    const fixture=join(cwd,'fixture.mjs');
    await writeFile(fixture,`import {makePiExtension} from ${JSON.stringify(fileURLToPath(new URL('./pi.mjs',import.meta.url)))};\nexport default function(pi){pi.registerProvider('fixture',{baseUrl:${JSON.stringify(srv.origin+'/v1')},apiKey:'fixture-local-only',api:'openai-completions',models:[{id:'local',name:'Local fixture',reasoning:false,input:['text'],cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:20000,maxTokens:100}]});makePiExtension({getKey:async()=> 'fixture-local-only',fetcher:(_url,args)=>fetch(${JSON.stringify(srv.origin+'/classify')},args)})(pi);}`);
    args=['--print','--offline','--no-extensions','--no-mcp','--no-context-files','--no-skills','--no-prompt-templates','--no-session','--no-tools','--extension',fixture,'--model','fixture/local',task];
   }else if(runtime==='gemini'){
    env.GEMINI_CLI_HOME=process.env.JEV_GEMINI_PROFILE?join(process.env.JEV_GEMINI_PROFILE,'state'):join(cwd,'gemini');env.GEMINI_API_KEY='fixture-local-only';env.GOOGLE_GEMINI_BASE_URL=srv.origin;env.GEMINI_TELEMETRY_ENABLED='false';env.GEMINI_CLI_NO_RELAUNCH='1';
    await mkdir(env.GEMINI_CLI_HOME,{recursive:true});const settings=join(env.GEMINI_CLI_HOME,'settings.json');env.GEMINI_CLI_SYSTEM_SETTINGS_PATH=settings;env.GEMINI_CLI_SYSTEM_DEFAULTS_PATH=join(cwd,'absent-defaults.json');
    await writeFile(settings,JSON.stringify({general:{enableAutoUpdate:false,enableAutoUpdateNotification:false,maxAttempts:1,retryFetchErrors:false},telemetry:{enabled:false},security:{auth:{selectedType:'gemini-api-key'}},mcpServers:{},hooksConfig:{enabled:true},hooks:{BeforeAgent:[{hooks:[{type:'command',command,timeout:60000}]}]}}));
    args=['--prompt',task,'--model','gemini-2.5-flash','--output-format','stream-json','--extensions','none','--approval-mode','plan'];
   }else if(runtime==='opencode'){
    const plugin=join(cwd,'plugin');await mkdir(plugin);
    // The host supplies its own SDK; no dependency install or network fetch.
    await writeFile(join(plugin,'index.ts'),`import {readFile,writeFile} from 'node:fs/promises';import {Plugin} from '@opencode/plugin';import {catalogueHash} from ${JSON.stringify(fileURLToPath(new URL('./agents.mjs',import.meta.url)))};import {setupOpenCode} from ${JSON.stringify(fileURLToPath(new URL('./opencode.mjs',import.meta.url)))};export default Plugin.define({id:'jev-local-fixture',async setup(ctx){await ctx.skill.transform(e=>{e.list().forEach(s=>e.remove(s.id));e.add({id:'optional-fixture',name:'optional-fixture',description:'Research ocean tides',path:${JSON.stringify(filePath)},content:'LOCAL-OPTIONAL-BODY-7d2f'});});await ctx.session.hook('prompt',async()=>{const {data}=await ctx.skill.list();const path=${JSON.stringify(policyPath)};const policy=JSON.parse(await readFile(path,'utf8'));policy.catalogueHash=catalogueHash(data.map(s=>({name:s.id,description:s.name===s.id?(s.description||''):s.name+': '+(s.description||''),filePath:s.path})));await writeFile(path,JSON.stringify(policy));});return setupOpenCode(ctx,{getKey:async()=> 'fixture-local-only',fetcher:(_url,args)=>fetch(${JSON.stringify(srv.origin+'/classify')},args)});}});`);
    await writeFile(join(cwd,'opencode.json'),JSON.stringify({update:'disable',share:'disabled',snapshots:false,lsp:false,formatter:false,model:'local/fixture',plugins:[plugin],providers:{local:{name:'Local fixture',package:'@opencode/ai/providers/openai-compatible',settings:{baseURL:srv.origin+'/v1',apiKey:'fixture-local-only'},models:{fixture:{name:'Local fixture'}}}}}));
    args=['run','--standalone','--print-logs','--log-level','debug','--format','json','--model','local/fixture',task];
   }else throw Error('Unknown native fixture runtime');
   const result=await launch(runtime,args,env,cwd);
   const jev=srv.events.filter(e=>e.path==='/classify'),models=srv.events.filter(e=>e.path!=='/classify');
   const model=models.find(e=>e.raw.includes('LOCAL-OPTIONAL-BODY-7d2f'));
   const observed=disabled?jev.length===0&&!model&&result.stdout.includes('LOCAL NATIVE ANSWER'):jev.length===1&&Boolean(model)&&jev[0].respondedAt<=model.at&&result.stdout.includes('LOCAL NATIVE ANSWER');
   const diagnostic=result.stderr.match(/(?:Jev|TypeSafe|local routing)[^\n]{0,200}/g)||[];
   report.push({runtime,version:execFileSync(runtime,['--version'],{encoding:'utf8'}).trim(),mode:disabled?'disabled':'routing',status:observed?'observed':'blocked',exit:result.exit,signal:result.signal,classifierCalls:jev.length,modelCalls:models.length,optionalBodyInModel:Boolean(model),order:observed&&!disabled?[{event:'Jev request/response',requestAt:jev[0].at,responseAt:jev[0].respondedAt},{event:'selected skill in native model request',requestAt:model.at,responseAt:model.respondedAt}]:[],diagnostic,output:result.stdout.slice(-5000),stderr:result.stderr.slice(-5000)});
   if(observed&&!disabled){const log=await readFile(policyPath+'.picks.jsonl','utf8');assert.ok(!log.includes(task)&&!log.includes('fixture-local-only'));}
  }finally{srv.close();}
 }
 console.log(JSON.stringify(report,null,2));
 if(output)await writeFile(resolve(output),JSON.stringify(report,null,2)+'\n');
 if(report.some(row=>row.status!=='observed'))process.exitCode=2;
}finally{await rm(work,{recursive:true,force:true});}
