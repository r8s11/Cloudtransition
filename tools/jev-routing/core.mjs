import { readFile, mkdir, open, chmod, lstat } from 'node:fs/promises';
import { dirname } from 'node:path';

export const MODEL = 'jev-1.14.0';
const RATE = .042 / 1e6;
const RESERVATION = 64000 * RATE;
const NONE = '__none__';

export function rejectSecrets(text) {
 if (/(?:api[_-]?key|password|secret|bearer)\s*[:=]\s*\S{8,}|\b(?:sk-[\w-]{12,}|gh[pousr]_[\w]{20,}|AKIA[A-Z0-9]{16})|-----BEGIN .*PRIVATE KEY-----/i.test(text)) throw new Error('Secret-like content blocked before transmission');
}

export class JevClient {
 constructor({key, consent=false, budget=0, fetcher=fetch, signal}) {
  this.key=key; this.consent=consent; this.budget=budget; this.fetcher=fetcher; this.signal=signal; this.spent=0; this.tokens=0; this.calls=0;
 }
 async ask(questions, state) {
  if(!this.consent) throw new Error('TypeSafe transmission not authorized');
  const body=JSON.stringify({model:MODEL,state,questions});rejectSecrets(JSON.stringify(state));
  if(!this.key) throw new Error('TypeSafe key unavailable');
  if(!Number.isFinite(this.budget)||this.spent+RESERVATION>this.budget) throw new Error('Jev budget exhausted');
  if(Buffer.byteLength(body)>100000) throw new Error('Jev request too large; no content was truncated');
  this.spent+=RESERVATION;this.calls++;
  let response;
  try { response=await this.fetcher('https://api.typesafe.ai/v1/systemone',{method:'POST',headers:{Authorization:`Bearer ${this.key}`,'Content-Type':'application/json'},body,signal:this.signal?AbortSignal.any([this.signal,AbortSignal.timeout(30000)]):AbortSignal.timeout(30000)}); }
  catch {throw new Error('Jev request failed (no automatic retry)');}
  if(!response.ok) throw new Error(`Jev HTTP ${response.status} (no automatic retry)`);
  let data;try{data=await response.json();}catch{throw new Error('Invalid Jev response');}
  if(data.model!==MODEL) throw new Error('Unexpected Jev response model');
  const tokens=data.usage?.input_tokens;
  if(!Number.isSafeInteger(tokens)||tokens<0||tokens>64000) throw new Error('Invalid Jev token usage');
  this.spent-=RESERVATION-tokens*RATE;this.tokens+=tokens;
  for(const [id,q] of Object.entries(questions)) {
   const a=data.answers?.[id];
   if(a?.type!=='choice'||!Object.hasOwn(q.criteria,a.choice)) throw new Error('Jev returned unknown choice');
  }
  return data.answers;
 }
}

// Full catalogue tournament: each round includes None, never compares probabilities
// from separate groups. Group winners receive a new jointly normalized Choice.
export async function choose(client, task, items, instructions='Which capability is the best fit for the user task? Choose None when none applies.', trace=()=>{}) {
 if(!items.length) return null;
 if(new Set(items.map(x=>x.name)).size!==items.length||items.some(x=>x.name===NONE)) throw new Error('Duplicate or reserved candidate name');
 rejectSecrets(task);
 let round=items,roundNo=0;
 for(;;) {
  const questions={};
  for(let i=0;i<round.length;i+=254){
   const criteria=Object.fromEntries(round.slice(i,i+254).map(x=>[x.name,x.description]));criteria[NONE]='None of the listed candidates is appropriate for this task.';
   questions[`group_${i/254}`]={type:'choice',instructions,criteria};
  }
  // Split transport as well as Choice groups so catalogue growth cannot overflow
  // a single request. Every original candidate remains represented.
  const winners=[];
  for(const [id,q] of Object.entries(questions)) {
   const a=(await client.ask({[id]:q},{task}))[id];
   if(!Object.hasOwn(q.criteria,a?.choice))throw new Error('Jev returned unknown choice');
   // Metadata only (no task text): lets tests prove coverage, option counts and arbitration.
   trace({round:roundNo,group:id,options:Object.keys(q.criteria).length,hasNone:Object.hasOwn(q.criteria,NONE),choice:a.choice===NONE?null:a.choice});
   if(a.choice!==NONE)winners.push(round.find(x=>x.name===a.choice));
  }
  if(!winners.length)return null;
  if(Object.keys(questions).length===1)return winners[0].name;
  round=winners;roundNo++;
 }
}

export function eligibleModels(models) {
 return models.filter(m=>['anthropic','openai','openai-codex'].includes(m.provider)&&(!m.kind||m.kind==='chat')).map(m=>({
  name:`${m.provider}/${m.id}`,
  description:JSON.stringify({name:m.name||m.id,company:m.provider==='anthropic'?'Anthropic':'OpenAI',reasoning:m.reasoning,contextWindow:m.contextWindow,cost:m.cost}),
  model:m,
 }));
}

export async function loadSkill(name, skills) {
 if(name===null)return '';
 const skill=skills.find(x=>x.name===name);if(!skill)throw new Error('Unknown selected skill');
 const body=await readFile(skill.filePath,'utf8');
 const front=body.match(/^---\s*\n([\s\S]*?)\n---/);
 const rawName=front?.[1].match(/^name:\s*["']?([^\n"']+)/m)?.[1]?.trim();
 // Omp collision aliases are namespaced; the raw frontmatter remains unqualified.
 if(rawName!==name&&rawName!==name.split('/').at(-1))throw new Error('Selected skill changed; rediscover before loading');
 return `[Selected skill: ${name}; directory: ${dirname(skill.filePath)}]\n${body}`;
}

export class PickLog {
 constructor(path){this.path=path;}
 async append(record){
  const dir=dirname(this.path);await mkdir(dir,{recursive:true,mode:0o700});
  if((await lstat(dir)).isSymbolicLink())throw new Error('Unsafe log directory');
  await chmod(dir,0o700);
  try{if((await lstat(this.path)).isSymbolicLink())throw new Error('Unsafe log file');}catch(e){if(e.code!=='ENOENT')throw e;}
  const safe={timestamp:new Date().toISOString()};
  for(const k of ['id','session','outcome','difficulty','model','skill','inputTokens','classifierUSD','helperUSD','errorCode'])if(record[k]!==undefined)safe[k]=record[k];
  const h=await open(this.path,'a',0o600);try{await h.chmod(0o600);await h.writeFile(JSON.stringify(safe)+'\n');await h.sync();}finally{await h.close();}
 }
}
