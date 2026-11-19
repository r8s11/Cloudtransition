import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, copyFile, writeFile, readdir, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {execFileSync, spawn} from 'node:child_process';
import {createBrainClient} from './core.mjs';
async function fixture(t){
 const root=await mkdtemp(join(tmpdir(),'brain-adapter-'));
 t.after(()=>rm(root,{recursive:true,force:true}));
 await mkdir(join(root,'second-brain'));
 await copyFile(resolve('second-brain/brain.py'),join(root,'second-brain/brain.py'));
 await writeFile(join(root,'CODE.md'),'# Integration fixture\n\nThe integration canary is amber kestrel.\n');
 execFileSync('python3',[join(root,'second-brain/brain.py'),'--root',root,'index']);
 return root;
}
test('validation and argv preserve the fixed memory boundary',async t=>{
 const root=await fixture(t), client=createBrainClient({root});
 const memory={title:'Integration preference',summary:'The editor theme is amber.',body:'The integration editor theme is amber.'};
 const inventory=async()=>{try{return await readdir(join(root,'second-brain/memories'));}catch{return [];}};
 const before=await inventory();
 for(const query of ['', 'x'.repeat(501)])assert.equal((await client.recall({query})).exitCode,2);
 for(const patch of [{title:'x'.repeat(121)},{summary:'x'.repeat(501)},{body:'x'.repeat(8001)},{supersedes:['unknown-id']},{body:'AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE'},{root:'/tmp/alternate'}]){
  assert.notEqual((await client.remember({...memory,...patch})).exitCode,0);
 }
 assert.deepEqual(await inventory(),before);
 const marker=join(root,'shell-marker');
 await client.recall({query:`integration; touch ${marker} $(touch ${marker})`});
 assert.ok(!(await readdir(root)).includes('shell-marker'));
 const saved=await client.remember(memory);
 assert.equal(saved.exitCode,0);assert.equal(saved.payload.indexed,true);
 const recalled=await client.recall({query:'integration editor theme'});
 assert.equal(recalled.exitCode,0);assert.match(JSON.stringify(recalled.payload),/amber/);
 const boundary=await client.remember({title:'t'.repeat(120),summary:'s'.repeat(500),body:'b'.repeat(8000)});
 assert.equal(boundary.exitCode,0);assert.equal(boundary.payload.indexed,true);
 assert.equal((await client.recall({query:'q'.repeat(500)})).exitCode,0);
});
test('subprocess failure and cancellation never acknowledge an unsaved memory',async t=>{
 const root=await fixture(t);
 const script=join(root,'second-brain/child.py');
 async function child(source,options={}){await writeFile(script,source);return createBrainClient({root,script,...options});}
 let client=await child('import time\ntime.sleep(60)\n',{timeoutMs:100});
 await assert.rejects(client.recall({query:'canary'}),{code:'timeout'});
 client=await child('import time\ntime.sleep(60)\n');
 const abort=new AbortController(), pending=client.remember({title:'Pending',summary:'Pending fact.',body:'Pending fact.'},{signal:abort.signal});
 setTimeout(()=>abort.abort(),100);await assert.rejects(pending,{code:'cancelled'});
 client=await child('print("x" * 5000)\n',{maxBuffer:100});
 await assert.rejects(client.recall({query:'canary'}),{code:'output_limit'});
 client=await child('print("not json")\n');await assert.rejects(client.recall({query:'canary'}),{code:'invalid_json'});
 client=await child('import sys\nprint("{}")\nsys.exit(20)\n');await assert.rejects(client.recall({query:'canary'}),{code:'process_failed'});
 client=createBrainClient({root,python:'/nonexistent/python'});await assert.rejects(client.recall({query:'canary'}),{code:'process_unavailable'});
 const lock=spawn('python3',['-u','-c','import fcntl,sys,time\nf=open(sys.argv[1],"w")\nfcntl.flock(f,fcntl.LOCK_EX)\nprint("locked",flush=True)\ntime.sleep(60)',join(root,'second-brain/.lock')]);
 try {
  await new Promise((resolve,reject)=>{lock.stdout.once('data',resolve);lock.once('error',reject);});
  const result=await createBrainClient({root}).remember({title:'Locked',summary:'Locked fact.',body:'Locked fact.'});
  assert.equal(result.exitCode,4);
 } finally {lock.kill('SIGKILL');}
 client=await child('import subprocess,sys,time\nsubprocess.run([sys.executable,sys.argv[0].replace("child.py","brain.py"),*sys.argv[1:]],check=True,stdout=subprocess.DEVNULL)\nprint("committed",flush=True)\ntime.sleep(60)\n',{timeoutMs:1500});
 await assert.rejects(client.remember({title:'Committed preference',summary:'The committed theme is jade.',body:'The committed theme is jade.'}),{code:'timeout'});
 const files=(await readdir(join(root,'second-brain/memories'))).filter(x=>x.endsWith('.md'));
 assert.equal(files.length,1);
 assert.match(await readFile(join(root,'second-brain/memories',files[0]),'utf8'),/jade/);
 const committed=await createBrainClient({root}).recall({query:'committed theme'});
 assert.equal(committed.exitCode,0);assert.match(JSON.stringify(committed.payload),/jade/);
});
