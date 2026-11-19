// Explicit local-fixture entry only; never install as a real routing hook.
import { promptHook } from './agents.mjs';
const cfg=JSON.parse(process.env.JEV_AGENT_FIXTURE||'{}');
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(cfg.origin||''))throw Error('Local fixture origin required');
let raw='';for await(const part of process.stdin)raw+=part;
const input=JSON.parse(raw);
console.log(JSON.stringify(await promptHook(process.argv[2],input,{getKey:async()=> 'fixture-local-only',fetcher:(_url,args)=>fetch(cfg.origin+'/classify',args)})));
