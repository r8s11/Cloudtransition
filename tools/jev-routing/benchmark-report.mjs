// Offline only: re-report the consumed, approved historical benchmark. Never calls Jev.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const root=new URL('../../docs/plans/jev-skill-routing/eval-evidence/',import.meta.url);
const read=async name=>JSON.parse(await readFile(new URL(name,root),'utf8'));
const [approved,results,authorization]=await Promise.all(['approved-benchmark.json','benchmark-results.json','authorization-source.json'].map(read));
assert.equal(approved.tasks.length,10);assert.equal(results.results.length,10);
assert.equal(authorization.approvalResponse.text,'User answers:\n{\n  "jev_live": "yes"\n}');
assert.ok(Date.parse(authorization.approvalResponse.at)<Date.parse(authorization.labelsSavedAt));
assert.ok(Date.parse(authorization.labelsSavedAt)<Date.parse(authorization.firstBenchmarkInvocationAt));
assert.equal(authorization.consumed,true);
const seen=new Set();
const rows=approved.tasks.map(task=>{
 assert.ok(!seen.has(task.text));seen.add(task.text);
 const result=results.results.find(r=>r.id===task.id);assert.ok(result);
 assert.deepEqual(result.expected,task.expected);
 const source=authorization.historicalTaskSources.find(s=>s.id===task.id);assert.ok(source?.record);assert.equal(source.session,task.sourceSession);
 const correct=!result.error&&task.expected.accepted.includes(result.actual);
 assert.equal(result.correct,correct);
 return {id:task.id,sourceSession:task.sourceSession,sourceAt:task.at,sourceRecord:source.record,sourceRecordAt:source.at,sourceMatch:source.match,expected:task.expected.accepted,ambiguous:task.expected.ambiguous,ambiguity:task.expected.reason,actual:result.actual,correct,error:result.error,inputTokens:result.input_tokens};
});
assert.equal(rows.reduce((n,r)=>n+r.inputTokens,0),results.total_input_tokens);
assert.ok(results.total_reserved_or_spent_usd<=approved.max_usd);
console.log(JSON.stringify({mode:'offline; no requests',authorization:fileURLToPath(new URL('authorization-source.json',root)),model:results.model,approvalConsumed:true,refreshAuthorized:false,rows,summary:{accepted:rows.filter(r=>r.correct).length,mismatches:rows.filter(r=>!r.correct&&!r.error).length,errors:rows.filter(r=>r.error).length,reportedInputTokens:results.total_input_tokens,reportedRequests:results.calls,spentOrReservedUSD:results.total_reserved_or_spent_usd,approvedCapUSD:approved.max_usd}},null,2));
