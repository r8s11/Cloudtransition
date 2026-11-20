import { routeApproved, OFF } from './agents.mjs';

export async function setupOpenCode(ctx,deps={}) {
 const registration=await ctx.session.hook('prompt',async event=>{
  const policyPath=deps.policyPath??process.env.JEV_SKILL_APPROVAL;
  if(!policyPath){event.prompt.text+=`\n\n${OFF}`;return;}
  if(event.prompt.files?.length)throw Error('Jev attachments need separate approval; no task sent');
  const {data:native}=await ctx.skill.list();
  const skills=native.map(s=>({name:s.id,description:s.name===s.id?(s.description||''):`${s.name}: ${s.description||''}`,filePath:s.path}));
  try {
   const loadSelected=async selected=>{
    if(selected===null)return '';
    const skill=native.find(s=>s.id===selected);
    if(!skill||typeof skill.content!=='string')throw Error('Jev selected native skill unavailable');
    return `[Selected skill: ${skill.id}; native path: ${skill.path}]\n${skill.content}`;
   };
   const result=await routeApproved({runtime:'opencode',session:event.sessionID,task:event.prompt.text,skills,policyPath,loadSelected,...deps});
   // Append, do not prepend: existing native attachment/agent mention offsets stay valid.
   event.prompt.text+=`\n\n${result.context}`;
  } catch(error) {
   const reason=/^(Jev|TypeSafe|Secret|Unknown selected|Selected skill|Duplicate)[^\n]{0,120}$/.test(error?.message||'')?error.message:'local routing integration failed';
   throw Error(`${reason}. No optional skill loaded; no fallback. Required instructions remain binding.`);
  }
 });
 return ()=>registration.dispose();
}
