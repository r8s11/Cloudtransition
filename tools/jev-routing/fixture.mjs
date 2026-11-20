// Explicit-test entry point only (loaded with `omp -e`); never installed in the user's extension directory.
// Every provider's base URL is redirected to the local fake server named in JEV_FIXTURE.origin.
import { makeExtension, runHelper, discoverSkills } from './extension.mjs';
import { PickLog } from './core.mjs';

export default function (pi) {
 const cfg = JSON.parse(process.env.JEV_FIXTURE || '{}');
 if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(cfg.origin || '')) throw Error('Local fixture origin required');
 const model = id => ({ id, name: id, reasoning: false, input: ['text'], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 200000, maxTokens: 1000 });
 const register = () => {
  for (const [provider, ids] of Object.entries(cfg.providers || {})) {
   pi.registerProvider(provider, { baseUrl: cfg.origin + '/v1', apiKey: 'fixture-local-only', api: 'openai-completions', models: ids.map(model) });
  }
 };
 register();
 // Helper SDK sessions refresh the shared registry; restore this test-only
 // catalogue before each subsequent input rather than exposing real models.
 pi.on('input', () => { register(); });
 const skills = cfg.skills || 'none';
 // real: the user's actual Omp skill catalogue; real-project: only skills under the test project's .omp/skills.
 const catalogue = skills === 'real' ? discoverSkills
  : skills === 'real-project' ? async cwd => (await discoverSkills(cwd)).filter(s => s.source === 'native:project')
  : async () => [];
 const discover = async cwd => { register(); return catalogue(cwd); };
 pi.registerCommand('fixture-status', {
  description: 'Local fixture command registered before Jev',
  handler: async () => pi.sendMessage({customType:'fixture',content:'Existing fixture command handled',display:true},{triggerTurn:false}),
 });
 makeExtension({
  getKey: async () => { if (cfg.key === null) throw Error('no key'); return cfg.key ?? 'fixture-local-only'; },
  discoverSkills: discover,
  runHelper: async a => { try { return await runHelper(a); } catch (e) { console.error('HELPER_ERROR', String(e?.message || e).slice(0, 300)); throw e; } },
  fetcher: (_url, args) => fetch(cfg.origin + '/classify', args),
  log: new PickLog(cfg.log),
 })(pi);
}
