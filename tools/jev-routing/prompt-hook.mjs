#!/usr/bin/env node
import { promptHook } from './agents.mjs';
let input='';
try {
 for await(const part of process.stdin){input+=part;if(Buffer.byteLength(input)>1024*1024)throw Error('Hook input too large');}
 console.log(JSON.stringify(await promptHook(process.argv[2],JSON.parse(input))));
} catch {
 console.log(JSON.stringify({continue:false,stopReason:'Jev hook input failed; no task transmitted or optional skill loaded.'}));
 process.exitCode=2;
}
