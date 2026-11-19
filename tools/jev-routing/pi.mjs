import { readFile } from 'node:fs/promises';
import { routeApproved, OFF } from './agents.mjs';

export function makePiExtension(deps={}) {
 return function(pi) {
  pi.on('input',async(event,ctx)=>{
   if(event.source==='extension'||event.text.trim().startsWith('/'))return;
   const policyPath=deps.policyPath??process.env.JEV_SKILL_APPROVAL;
   if(!policyPath){ctx.ui.notify(OFF,'info');return;}
   try {
    if(event.images?.length)throw Error('Attachments need separate approval');
    const skills=deps.skills??JSON.parse(await readFile(process.env.JEV_SKILL_CATALOGUE,'utf8'));
    const result=await routeApproved({runtime:'pi',session:ctx.sessionManager.getSessionId(),task:event.text,skills,policyPath,...deps});
    return {action:'transform',text:`${result.context}\n\n${event.text}`,images:event.images};
   } catch {
    ctx.ui.notify('Jev skill routing failed or lacks exact data/spend approval. Message blocked; no optional skill or fallback. Required instructions remain binding.','error');
    return {action:'handled'};
   }
  });
 };
}
export default makePiExtension();
