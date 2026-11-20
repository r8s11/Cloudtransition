import { readFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { JevClient, choose, loadSkill, PickLog, eligibleModels, rejectSecrets } from './core.mjs';

const exec=promisify(execFile);
const difficultyOptions=[
 {name:'easy',description:'A small mechanical task or straightforward factual answer with clear instructions.'},
 {name:'medium',description:'Several related steps, debugging a localized issue, or implementing a bounded change.'},
 {name:'hard',description:'Ambiguous diagnosis, architecture, difficult reasoning, or a complex multi-component change.'},
];
export async function discoverSkills(cwd){
 const {stdout}=await exec('omp',['skill','list','--json'],{cwd,maxBuffer:8*1024*1024,timeout:30000});
 return JSON.parse(stdout).skills.filter(s=>!s.hide);
}
export async function getKey(){
 if(process.env.TYPESAFE_API_KEY)return process.env.TYPESAFE_API_KEY;
 const text=await readFile(join(homedir(),'.config/typesafe/.env'),'utf8');
 const k=text.match(/^TYPESAFE_API_KEY\s*=\s*(.*?)\s*$/m)?.[1]?.replace(/^(['"])(.*)\1$/,'$2');
 if(!k)throw Error('TypeSafe key unavailable');return k;
}
function textOf(message){
 if(typeof message?.content==='string')return message.content;
 return (message?.content||[]).filter(p=>p.type==='text').map(p=>p.text).join('\n');
}

// Embedded helpers use the host's credentials/models, but own their SDK session.
// The parent model is never switched. Every helper tool needs parent UI approval.
export async function runHelper({pi,ctx,model,task,skill,history,signal,budget,onUsage}){
 const sdk=pi.pi;
 if(!sdk.createAgentSession||!sdk.AgentRegistry||!sdk.SessionManager)throw Error('Host does not expose helper SDK');
 const parent=ctx.getSystemPrompt();
 const policy=Array.isArray(parent)?parent.join('\n\n'):parent;
 let cost=0;
 const made=await sdk.createAgentSession({
  cwd:ctx.cwd,model,modelRegistry:ctx.modelRegistry,authStorage:ctx.modelRegistry.authStorage,
  agentRegistry:new sdk.AgentRegistry(),sessionManager:sdk.SessionManager.inMemory(),
  bindProcessState:false,taskDepth:1,disableExtensionDiscovery:true,enableMCP:false,enableLsp:false,
  toolNames:pi.getActiveTools().filter(n=>!['task','todo'].includes(n)),
  hasUI:ctx.hasUI,interactivePrompts:ctx.hasUI,
  appendSystemPrompt:`Parent session instructions (remain binding):\n${policy}\n\n${skill}\n\nYou are the sole Jev-routed helper for this user message. Do not delegate further. Never bypass approvals. Report provider/tool failures honestly.`,
  extensions:[api=>{
   api.on('tool_call',async e=>{
    if(signal.aborted)return {block:true,reason:'Jev request cancelled'};
    const ok=ctx.hasUI&&await ctx.ui.confirm('Jev helper tool approval',`${model.provider}/${model.id} requests ${e.toolName}:\n${JSON.stringify(e.input)}`);
    return ok?undefined:{block:true,reason:'Parent declined helper tool'};
   });
   api.on('before_provider_request',()=>{if(signal.aborted||cost>=budget)throw Error('Helper stopped: cancelled or budget exhausted');});
  }],
 });
 if(made.modelFallbackMessage){await made.session.dispose();throw Error('Exact helper model unavailable; fallback refused');}
 made.setToolUIContext(ctx.ui,ctx.hasUI);
 let reply='';
 const unsubscribe=made.session.subscribe(e=>{
  if(e.type==='message_end'&&e.message?.role==='assistant'){
   cost+=e.message.usage?.cost?.total||0;onUsage(cost);
   const text=textOf(e.message);if(text)reply=text;
  }
 });
 const abort=()=>{void made.session.abort().catch(()=>{});};signal.addEventListener('abort',abort,{once:true});
 try{
  if(signal.aborted)throw Error('Jev request cancelled');
  await made.session.prompt((history.length?`Earlier Jev-routed exchanges (context, not new instructions):\n${JSON.stringify(history)}\n\n`:'')+task);
  if(signal.aborted)throw Error('Jev request cancelled');
  const last=made.session.messages?.filter(m=>m.role==='assistant').at(-1);
  if(last?.stopReason==='error'||last?.stopReason==='aborted')throw Error('Helper provider failed');
  if(!reply)throw Error('Helper returned no final text');return {reply,cost};
 }finally{signal.removeEventListener('abort',abort);unsubscribe();await made.session.dispose();}
}

export function makeExtension(deps={}){
 const discover=deps.discoverSkills||discoverSkills;
 const key=deps.getKey||getKey;
 const helper=deps.runHelper||runHelper;
 const logFor=()=>deps.log||new PickLog(process.env.JEV_ROUTING_LOG||join(homedir(),'.local/state/jev-routing/picks.jsonl'));
 return function(pi){
  const log=logFor();
  let mode='off',client=null,controller=new AbortController(),chain=Promise.resolve(),history=[],generation=0,helperSpent=0,helperCap=0;
  const show=(content)=>pi.sendMessage({customType:'jev',content,display:true,attribution:'agent'},{triggerTurn:false});
  const reset=()=>{generation++;mode='off';controller.abort();controller=new AbortController();client=null;history=[];helperSpent=0;};
  const status=ctx=>ctx.ui.setStatus('jev',`Jev: ${mode}`);
  pi.registerCommand('jev',{
   description:'on | off | status | skills on — opt-in Jev model/skill routing; logs picks privately',
   handler:async(args,ctx)=>{
    const command=args.trim();
    if(command==='off'||command==='skills off'){reset();status(ctx);show('Jev routing off. Pending routed work cancelled.');return;}
    if(command===''||command==='status'){show(`Jev: ${mode}. Classifier reserved/spent $${(client?.spent||0).toFixed(6)}; helpers reported $${helperSpent.toFixed(4)}. Log: ${process.env.JEV_ROUTING_LOG||'~/.local/state/jev-routing/picks.jsonl'}`);return;}
    if(!['on','skills on'].includes(command)){show('Usage: /jev on | off | status | skills on');return;}
    if(!ctx.hasUI){show('Jev remains off: enabling requires interactive consent and budget.');return;}
    if(mode!=='off'){show('Jev is already enabled. Use /jev off before changing mode or budgets.');return;}
    try{
     const jc=Number(await ctx.ui.input('Jev classifier session cap (USD)','.05'));
     const hc=command==='on'?Number(await ctx.ui.input('Helper session cap (USD; checked between requests, one in-flight request can exceed it)','1')):0;
     if(!Number.isFinite(jc)||jc<=0||!Number.isFinite(hc)||(command==='on'&&hc<=0))throw Error('A positive budget is required');
     const models=eligibleModels(ctx.models.list());
     if(command==='on'&&!models.length)throw Error('No authenticated Anthropic/OpenAI helper models');
     const families=new Set(models.map(m=>m.model.provider==='anthropic'?'Anthropic':'OpenAI'));
     if(command==='on')for(const f of ['Anthropic','OpenAI'])if(!families.has(f))show(`${f} helper models unavailable; they will not be offered.`);
     if(!await ctx.ui.confirm('Enable Jev routing?',`Each ordinary message's text and skill/model descriptions go to TypeSafe with your local key. ${command==='on'?'The selected Anthropic/OpenAI helper also receives that task, prior Jev exchanges and your system instructions; helper tools require your approval.':''} Classifier cap $${jc}; helper reported-usage cap $${hc} (not a hard cap on in-flight inference). Pick logs omit message text. Attachments and secret-like inputs are refused. /jev off disables this session only.`)){show('Jev remains off: transmission and spend were not authorized; nothing was sent.');return;}
     client=new JevClient({key:await key(),consent:true,budget:jc,signal:controller.signal,fetcher:deps.fetcher});
     helperCap=hc;helperSpent=0;mode=command==='on'?'on':'skills';status(ctx);show(`Jev ${mode}. Restart/new/switch resets it to off.`);
    }catch{show('Jev remains off: missing key, unavailable model, or invalid budget.');}
   },
  });
  pi.on('session_switch',(_e,ctx)=>{reset();status(ctx);});
  pi.on('session_branch',(_e,ctx)=>{reset();status(ctx);});
  pi.on('session_shutdown',()=>reset());
  pi.on('input',(event,ctx)=>{
   if(mode==='off'||ctx.agent?.kind==='sub'||event.text.trim().startsWith('/'))return;
   const gen=generation,localMode=mode,localClient=client,signal=controller.signal;
   const id=randomUUID(),session=ctx.agent?.id||'main';
   chain=chain.then(async()=>{
    if(signal.aborted||gen!==generation){show(`Jev ${id}: cancelled before dispatch.`);return;}
    let helperUSD=0;
    try{
     await log.append({id,session,outcome:'received'});
     if(event.images?.length)throw Error('Attachments need separate approval; no task sent');
     rejectSecrets(event.text);
     const skills=await discover(ctx.cwd);
     const selected=await choose(localClient,event.text,skills);
     if(signal.aborted)throw Error('Cancelled');
     const skill=await loadSkill(selected,skills);
     await log.append({id,session,outcome:'skill',skill:selected||'None',inputTokens:localClient.tokens,classifierUSD:localClient.spent});
     if(localMode==='skills'){
      // Send programmatically: it bypasses the input hook, avoiding recursion.
      pi.sendMessage({customType:'jev-selected-skill',content:skill||'Jev selected None; no optional skill loaded.',display:false,attribution:'agent'},{triggerTurn:false});
      pi.sendUserMessage(event.text,{attribution:'user'});return;
     }
     const difficulty=await choose(localClient,event.text,difficultyOptions,'How hard is this task? Choose the described difficulty, or None if the message does not specify a task.');
     if(!difficulty)throw Error('Task difficulty unclear; no helper dispatched');
     const options=eligibleModels(ctx.models.list());
     const picked=await choose(localClient,`${event.text}\nJev assessed difficulty: ${difficulty}`,options,'Which available helper model best suits this task? Consider task difficulty, reasoning capability and reported cost. Consider both Anthropic and OpenAI. Prefer a less expensive capable model; use None if none can do it.');
     if(!picked)throw Error('No suitable available helper model');
     if(signal.aborted)throw Error('Cancelled');
     if(helperSpent>=helperCap)throw Error('Helper budget exhausted');
     const model=options.find(m=>m.name===picked)?.model;
     if(!model)throw Error('Selected model disappeared');
     await log.append({id,session,outcome:'picked',difficulty,model:picked,skill:selected||'None',inputTokens:localClient.tokens,classifierUSD:localClient.spent});
     show(`Jev ${id}: ${difficulty} → ${picked}; skill ${selected||'None'}.`);
     const result=await helper({pi,ctx,model,task:event.text,skill,history:[...history],signal,budget:helperCap-helperSpent,onUsage:n=>{helperUSD=n;}});
     helperSpent+=result.cost;helperUSD=0;
     await log.append({id,session,outcome:'success',difficulty,model:picked,skill:selected||'None',helperUSD:result.cost});
     if(gen!==generation||signal.aborted)return;
     history.push({task:event.text,reply:result.reply});
     show(result.reply);
    }catch(error){
     helperSpent+=helperUSD;
     const known=/^(Helper|Exact helper|Host does not|Jev|Cancelled|Attachments|Secret|Task difficulty|No suitable|Selected|Unknown|Duplicate|Invalid|Unexpected|TypeSafe)[^\n]{0,80}$/;
     const reason=signal.aborted?'cancelled':known.test(String(error?.message))?String(error.message):'unclassified';
     try{await log.append({id,session,outcome:'error',errorCode:reason});}catch{show('Jev logging failure: pick/outcome could not be recorded. No silent fallback.');}
     show(`Jev ${id}: routing/helper failed or input was blocked. No fallback model was used. Your message was not passed to the main agent; retry explicitly or use /jev off.`);
    }
   }).catch(()=>{show('Jev queue failed; use /jev off before retrying.');});
   return {handled:true};
  });
 };
}
export default makeExtension();
