// Installed into the default profile only. Keep this loader on the internal disk.
import type { ExtensionAPI } from '@oh-my-pi/pi-coding-agent';
export default async function (pi: ExtensionAPI) {
  let extension;
  try {
    // External storage may be unmounted; a static import would prevent graceful startup.
    extension = await import('/Volumes/SANDISK USB/work/Cloudtransition/tools/second-brain-memory/extension.mjs');
  } catch {
    for (const name of ['second_brain_recall', 'second_brain_remember']) {
      pi.registerTool({
        name, label: 'Second Brain unavailable',
        description: 'Shared memory storage is unavailable. No fallback or automatic retry is used.',
        parameters: pi.zod.object({}).passthrough(),
        async execute() {
          return {isError: true, content: [{type: 'text', text: 'Second Brain storage unavailable. Mount the configured drive and restart OMP. No fallback store was created.'}]};
        },
      });
    }
    return;
  }
  extension.default(pi);
}
