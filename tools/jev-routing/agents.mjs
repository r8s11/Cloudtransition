import { readFile, open, unlink } from 'node:fs/promises';
import { constants } from 'node:fs';
import { createHash, randomUUID } from 'node:crypto';
import { JevClient, choose, loadSkill, PickLog, rejectSecrets } from './core.mjs';
import { getKey } from './extension.mjs';

export const taskHash=text=>createHash('sha256').update(text).digest('hex');
export const catalogueHash=skills=>taskHash(JSON.stringify(skills.map(({name,description,filePath})=>({name,description,filePath})).sort((a,b)=>a.name.localeCompare(b.name))));
export const PRECEDENCE='Required skills and higher-priority instructions remain binding. Jev selects only an optional skill; None does not suppress required skills or approvals.';
export const OFF='Jev skill routing off: no reviewed approval file configured. Native required skills and existing workflows remain active.';
const readJSON=async path=>JSON.parse(await readFile(path,'utf8'));

// Each process shares the same approval ledger. Reserve before transmission, retain
// reservations on failure, and refuse concurrency rather than race the approved cap.
// shortcut: a hook killed mid-request leaves <policy>.lock and blocks routing until it is deleted; add pid-liveness if that happens in practice.
export async function routeApproved({runtime,session,task,skills,policyPath=process.env.JEV_SKILL_APPROVAL,getKey:key=getKey,fetcher=fetch,loadSelected=loadSkill}) {
 if(!policyPath)return {disabled:true,context:OFF};
 const lock=await open(policyPath+'.lock','wx',0o600).catch(()=>{throw Error('Jev approval ledger unavailable or busy');});
 let client,log,id;
 const usagePath=policyPath+'.usage.json';
 const save=async()=>{
  const file=await open(usagePath,constants.O_WRONLY|constants.O_CREAT|constants.O_TRUNC|constants.O_NOFOLLOW,0o600);
  try{await file.chmod(0o600);await file.writeFile(JSON.stringify({spent:client.spent,tokens:client.tokens,calls:client.calls}));await file.sync();}finally{await file.close();}
 };
 try {
  const policy=await readJSON(policyPath);
  if(policy.approved!==true||!Array.isArray(policy.runtimes)||!policy.runtimes.includes(runtime)||typeof policy.expires!=='string'||!(Date.parse(policy.expires)>Date.now())||!Array.isArray(policy.taskHashes)||!policy.taskHashes.includes(taskHash(task)))throw Error('Jev task transmission not authorized');
  if(policy.catalogueHash!==catalogueHash(skills))throw Error('Jev approved catalogue changed');
  if(!Number.isFinite(policy.maxUSD)||policy.maxUSD<=0)throw Error('Jev positive budget required');
  rejectSecrets(task);rejectSecrets(JSON.stringify(skills.map(({name,description})=>({name,description}))));
  let previous={spent:0,tokens:0,calls:0};
  try{previous=await readJSON(usagePath);}catch(e){if(e.code!=='ENOENT')throw Error('Jev approval ledger invalid');}
  if(!Number.isFinite(previous.spent)||previous.spent<0||!Number.isSafeInteger(previous.tokens)||previous.tokens<0||!Number.isSafeInteger(previous.calls)||previous.calls<0)throw Error('Jev approval ledger invalid');
  log=new PickLog(policyPath+'.picks.jsonl');id=randomUUID();
  await log.append({id,session:`${runtime}:${session}`,outcome:'received'});
  client=new JevClient({key:await key(),consent:true,budget:policy.maxUSD,fetcher:async(url,args)=>{await save();return fetcher(url,args);}});
  Object.assign(client,{spent:previous.spent,tokens:previous.tokens,calls:previous.calls});
  const selected=await choose(client,task,skills);
  const body=await loadSelected(selected,skills);
  await save();
  await log.append({id,session:`${runtime}:${session}`,outcome:'skill',skill:selected||'None',inputTokens:client.tokens,classifierUSD:client.spent});
  return {selected,context:`${PRECEDENCE}\n\n${body||'Jev selected None; no optional skill loaded.'}`};
 } catch(error) {
  if(client)await save();
  if(log&&id)await log.append({id,session:`${runtime}:${session}`,outcome:'error',errorCode:'Routing blocked; no fallback or optional skill loaded'});
  throw error;
 } finally {await lock.close();await unlink(policyPath+'.lock');}
}

// Claude Code and Codex share the UserPromptSubmit wire contract. Gemini uses
// BeforeAgent with the same additionalContext field and a different deny value.
export async function promptHook(runtime,input,deps={}) {
 const event=runtime==='gemini'?'BeforeAgent':'UserPromptSubmit';
 try {
  if(!['claude','codex','gemini'].includes(runtime)||input.hook_event_name!==event||typeof input.prompt!=='string'||!input.session_id)throw Error('Invalid Jev hook input');
  const policyPath=deps.policyPath??process.env.JEV_SKILL_APPROVAL;
  if(!policyPath)return {hookSpecificOutput:{hookEventName:event,additionalContext:OFF}};
  const skills=deps.skills??await readJSON(process.env.JEV_SKILL_CATALOGUE);
  const result=await routeApproved({runtime,session:input.session_id,task:input.prompt,skills,policyPath,...deps});
  return {hookSpecificOutput:{hookEventName:event,additionalContext:result.context}};
 } catch {
  return {decision:runtime==='gemini'?'deny':'block',reason:'Jev skill routing failed or lacks exact data/spend approval. No optional skill was loaded; no fallback was used. Required instructions remain binding.'};
 }
}
