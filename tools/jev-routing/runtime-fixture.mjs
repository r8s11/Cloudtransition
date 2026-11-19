// Explicit-test entry point only; never installed into the user's extension directory.
import { makeExtension, runHelper } from './extension.mjs';
import { PickLog } from './core.mjs';
export default function(pi){
 const base=process.env.JEV_SMOKE_ORIGIN;
 if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(base||''))throw Error('Local smoke origin required');
 for(const provider of ['anthropic','openai'])pi.registerProvider(provider,{
  baseUrl:base+'/v1',apiKey:'fixture-local-only',api:'openai-completions',
  models:[{id:'jev-fixture',name:'Local routing fixture',reasoning:false,input:['text'],cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:200000,maxTokens:1000}],
 });
 makeExtension({
  getKey:async()=> 'fixture-local-only',discoverSkills:async()=>[],runHelper:async a=>{try{return await runHelper(a);}catch(e){console.error('HELPER_ERROR',String(e?.stack||e).slice(0,1200));throw e;}},
  fetcher:(_url,args)=>fetch(base+'/classify',args),
  log:new PickLog(process.env.JEV_SMOKE_LOG),
 })(pi);
}
