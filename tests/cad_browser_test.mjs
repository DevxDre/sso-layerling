/* Real Chromium, only local synthetic accounts. No browser libraries/packages required. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
let input='';for await(const chunk of process.stdin)input+=chunk;
const fixture=JSON.parse(input);
assert.match(fixture.origin,/^http:\/\/127\.0\.0\.1:\d+$/);
const demoStop = new AbortController();
if (fixture.demo) process.once('SIGTERM', () => demoStop.abort());
const profile=await mkdtemp(join(tmpdir(),'sso-cad-chrome-'));
const chrome=spawn(process.env.SSO_CAD_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',[
  ...(fixture.demo ? [] : ['--headless=new', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']),
  '--no-first-run','--no-default-browser-check','--disable-background-networking',
  '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{stdio:'ignore'});
let stage='startup';let ws;let sequence=0;const pending=new Map();const errors=[];
const manifestRequests = [];
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function command(method,params={}){return new Promise((resolve,reject)=>{
  const id=++sequence;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout '+method));},20000);
  pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value);},reject:error=>{clearTimeout(timer);reject(error);}});ws.send(JSON.stringify({id,method,params}));
});}
async function evaluate(expression){const r=await command('Runtime.evaluate',{expression:'(async()=>('+expression+'))()',awaitPromise:true,returnByValue:true,userGesture:true});
  if(r.exceptionDetails)throw new Error('Browser evaluation failed: '+(r.exceptionDetails.exception?.description?.split('\n')[0] ?? r.exceptionDetails.text));return r.result.value;}
async function waitFor(expression,label,timeout=45000){const end=Date.now()+timeout;while(Date.now()<end){if(await evaluate(expression))return;await delay(150);}throw new Error('Timeout: '+label);}
async function cookies(values){for(const[name,value]of Object.entries(values))await command('Network.setCookie',{name,value,url:fixture.origin+'/',httpOnly:true,sameSite:'Lax'});}
async function navigate(path){await command('Page.navigate',{url:fixture.origin+path});await waitFor("document.readyState==='complete' && document.documentElement.dataset.ssoCad==='ready'",'editor online');}
async function checkNarrowPage() {
  for (const width of [320, 390]) {
    await command('Emulation.setDeviceMetricsOverride', {width, height:844, deviceScaleFactor:1, mobile:false});
    assert.equal(await evaluate('document.documentElement.scrollWidth'), width, 'page fits at ' + width + 'px');
  }
}

async function testAccount() {
  await evaluate("document.querySelector('.sso-topbar a[href=\"/konto/\"]').click()");
  await waitFor("location.pathname === '/konto/' && document.querySelector('.sso-brand img')?.naturalWidth > 0", 'account page with Layerling logo');
  const profile = await evaluate("[...document.querySelectorAll('.sso-card > .sso-account-data > dd')].map(field => field.textContent)");
  assert.deepEqual(profile, [fixture.accountName, fixture.accountId, '–']);
  const details = "document.querySelector('.sso-account-details')";
  assert.equal(await evaluate(details + '.open'), false, 'technical details are initially collapsed');
  await evaluate(details + ".querySelector('summary').click()");
  assert.equal(await evaluate(details + '.open'), true, 'technical details can be expanded');
  await checkNarrowPage();
  await evaluate("document.querySelector('form[action=\"/auth/logout.php\"] button').click()");
  const login = "document.querySelector('form[action=\"/auth/start.php\"] button')";
  await waitFor("location.pathname === '/index.php' && " + login + "?.classList.contains('sso-button-primary')", 'account logout returns to the styled manual sign-in');
  await checkNarrowPage();
}

async function testPermissions() {
  await cookies(fixture.adminCookies);
  await command('Page.navigate', {url: fixture.origin + '/rechte.php'});
  await waitFor("document.querySelector('.sso-brand img')?.naturalWidth > 0", 'rights page with Layerling logo');
  await checkNarrowPage();
  const actor = 'group:' + 'Konstruktionswerkstatt'.repeat(5);
  await evaluate(`(() => {
    const field = document.querySelector('#accounts-actor');
    field.value = ${JSON.stringify(actor)};
    field.form.elements.owner.value = 'role:target-fixture';
    field.form.requestSubmit();
  })()`);
  await waitFor("location.search === '?saved=1' && document.querySelector('.sso-rule-table')?.textContent.includes("
    + JSON.stringify(actor) + ')', 'saved rule is displayed with its full group ID');
  await checkNarrowPage();
  assert.equal(await evaluate("getComputedStyle(document.querySelector('.sso-rule-label')).display"), 'block', 'mobile cells have labels');

  await evaluate(`(() => {
    const field = document.querySelector('#group-pattern');
    field.value = '.*';
    field.form.requestSubmit(field.form.querySelector('button'));
  })()`);
  await waitFor("document.readyState === 'complete' && document.querySelector('#group-pattern-error') !== null", 'invalid pattern has field feedback');
  assert.equal(await evaluate("document.querySelector('#group-pattern').value"), '.*');
  await waitFor("document.activeElement.id === 'group-pattern'", 'focus returns to the invalid field');
  const pattern = 'konstruktionswerkstatt'.repeat(5) + '^';
  await evaluate(`(() => {
    const field = document.querySelector('#group-pattern');
    field.value = ${JSON.stringify(pattern)};
    field.form.requestSubmit(field.form.querySelector('button'));
  })()`);
  await waitFor("document.querySelector('.sso-patterns code')?.textContent === " + JSON.stringify(pattern), 'corrected filter is saved');
  await checkNarrowPage();
  await command('Emulation.setDeviceMetricsOverride', {width:1280, height:900, deviceScaleFactor:1, mobile:false});
  assert.equal(await evaluate("getComputedStyle(document.querySelector('.sso-rule-table')).display"), 'table', 'desktop uses a table');
}
async function enterSearch(value) {
  await evaluate(`(() => {
    const field = document.activeElement;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(field, ${JSON.stringify(value)});
    field.dispatchEvent(new Event('input', {bubbles: true}));
  })()`);
}
async function readDownload(fileName) {
  for (let attempt = 0; attempt < 160; attempt++) {
    try {
      return await readFile(join(profile, fileName), 'utf8');
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      await delay(150);
    }
  }
  throw new Error('Expected browser download: ' + fileName);
}
async function openFooter() {
  await waitFor("document.querySelector('#sso-cad-footer > details')!==null", 'SSO footer');
  await evaluate("(document.querySelector('#sso-cad-footer > details').open = true)");
}
async function openAccounts() {
  await openFooter();
  await evaluate("(document.getElementById('sso-cad-accounts').open = true)");
  await waitFor("document.activeElement.matches('#sso-cad-accounts input[type=search]')", 'account filter focus');
}
async function focusDesignSearch() {
  await openFooter();
  await waitFor("document.querySelector('#sso-cad-find-design')?.getClientRects().length > 0", 'design search shortcut');
  await evaluate("document.getElementById('sso-cad-find-design').click()");
  assert.equal(await evaluate("document.activeElement.hasAttribute('data-sso-design-search')"), true);
}
async function addBox(x) {
  await waitFor("document.querySelector('button[aria-label=\"Form hinzufügen\"],button[aria-label=\"Add shape\"]')!==null",'shape control');
  await evaluate("document.querySelector('button[aria-label=\"Form hinzufügen\"],button[aria-label=\"Add shape\"]').click()");
  await waitFor("Array.from(document.querySelectorAll('button')).some(b=>/^(Quader|Box)$/.test(b.getAttribute('aria-label')||b.title||b.textContent))",'box control');
  await evaluate("Array.from(document.querySelectorAll('button')).find(b=>/^(Quader|Box)$/.test(b.getAttribute('aria-label')||b.title||b.textContent)).click()");
  await waitFor("document.querySelector('.workplane-wrap.cruising')!==null",'placement active');
  const canvas=await evaluate("(()=>{const r=document.querySelector('.three-workplane-host canvas').getBoundingClientRect();return{x:r.x+r.width*"+x+",y:r.y+r.height*0.55};})()");
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...canvas});
  await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...canvas});
  await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...canvas});
}

function mcpCall(token, name, args = {}) {
  return new Promise((resolve, reject) => {
    const client = spawn(process.execPath, [fixture.mcp], {
      env: {...process.env, LAYERLING_URL: fixture.origin, LAYERLING_MCP_TOKEN: token, LAYERLING_MCP_OPEN_EDITOR: '0'},
      stdio: ['pipe', 'pipe', 'ignore'],
    });
    let output = '';
    const timeout = setTimeout(() => client.kill(), 20000);
    client.stdout.setEncoding('utf8');
    client.stdout.on('data', chunk => { output += chunk; });
    client.on('error', reject);
    client.on('close', code => {
      clearTimeout(timeout);
      try {
        assert.equal(code, 0, 'MCP stdio client exit');
        resolve(JSON.parse(output).result);
      } catch (error) { reject(error); }
    });
    client.stdin.end(JSON.stringify({jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: {name, arguments: args}}) + '\n');
  });
}

async function testMcp() {
  stage = 'MCP open editor';
  const create = "Array.from(document.querySelectorAll('button')).find(b=>/create new 3d design|neuen 3d.*(?:anlegen|erstellen)/i.test(b.textContent))";
  await waitFor(create + ' !== undefined', 'create control');
  await evaluate(create + '.click()');
  await waitFor("location.search.includes('editor=1') && document.querySelector('.three-workplane-host canvas')!==null", 'editor opened');
  stage = 'MCP token in SSO menu';
  await openFooter();
  await evaluate("document.getElementById('sso-mcp-pair').click()");
  const tokenField = "document.querySelector('input[aria-label=\"MCP-Testtoken\"]')";
  await waitFor(`${tokenField}.value.length === 64`, 'MCP token issued');
  const token = await evaluate(tokenField + '.value');
  const call = async (name, args) => {
    stage = name;
    const result = await mcpCall(token, name, args);
    assert.ok(!result.isError, `${name} succeeded: ${result.content[0].text}`);
    return JSON.parse(result.content[0].text);
  };
  const {editors} = await call('layerling_list_editors');
  assert.equal(editors.length, 1);
  const {editorNumber} = editors[0];
  const ownProjects = "(await (await fetch('/store.php')).json()).projects";
  await waitFor(ownProjects + "?.length === 1", 'new project saved in the paired account');
  const previousRevision = await evaluate(ownProjects + "[0].revision");
  const before = await call('layerling_read_scene', {editorNumber});
  await call('layerling_create_shape', {editorNumber, kind: 'box', width: 10, depth: 12, height: 8});
  const after = await call('layerling_read_scene', {editorNumber});
  assert.equal(after.shapeCount, before.shapeCount + 1);
  await waitFor(ownProjects + '[0].revision !== ' + JSON.stringify(previousRevision),
    'MCP shape persisted in the paired account');

  stage = 'MCP logout';
  await openFooter();
  await evaluate("setTimeout(() => document.querySelector('#sso-cad-nav button[type=submit]').click(), 0)");
  await waitFor("location.pathname==='/index.php' && document.querySelector('form[action=\"/auth/start.php\"]')!==null", 'logout');
  assert.equal((await mcpCall(token, 'layerling_list_editors')).isError, true);
  assert.deepEqual(errors, [], 'no uncaught browser errors');
  process.stdout.write('CAD_MCP_BROWSER_OK\n');
}

try{
  let port;for(let i=0;i<100;i++){try{port=Number((await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}catch{await delay(100);}}
  assert.ok(port,'Chrome debug port');
  const targets=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  ws.onmessage=({data})=>{const r=JSON.parse(data);if(r.id){const p=pending.get(r.id);if(p){pending.delete(r.id);r.error?p.reject(new Error(r.error.message)):p.resolve(r.result);}}
    else if(r.method==='Fetch.requestPaused') {
      const params=r.params;
      const query=new URL(params.request.url).searchParams;
      const failedUpload=params.request.method==='POST' && query.has('fileName');
      const failedSearch=params.request.method==='GET' && query.get('search')==='fixture-failure';
      const call=failedUpload || failedSearch
        ? command('Fetch.fulfillRequest',{requestId:params.requestId,responseCode:failedUpload ? 500 : 503,responseHeaders:[{name:'Content-Type',value:'application/json'}],body:Buffer.from(JSON.stringify({error:failedUpload ? 'fixture upload failure' : 'fixture search failure'})).toString('base64')})
        : command('Fetch.continueRequest',{requestId:params.requestId});
      void call.catch(()=>errors.push('Test interception failed'));
    }
    else if (r.method === 'Network.requestWillBeSent' && new URL(r.params.request.url).pathname === '/manifest.webmanifest') {
      manifestRequests.push(r.params.request.url);
    }
    else if(r.method==='Runtime.exceptionThrown')errors.push(r.params.exceptionDetails.text);
    else if(r.method==='Log.entryAdded' && r.params.entry.source==='security' && r.params.entry.level==='error')errors.push('Browser security error during '+stage+': '+r.params.entry.text.slice(0,320).replace(/nonce-[^' ]+/g,'nonce-[redacted]'));
  };
  await command('Page.enable');await command('Runtime.enable');await command('Log.enable');await command('Network.enable');
  await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await command('Page.addScriptToEvaluateOnNewDocument',{source:"try{localStorage.setItem('sso-unscoped-probe','legacy-only')}catch{}"});
  await cookies(fixture.cookies);await navigate('/');
  if (fixture.demo) {
    console.log(`CAD-Teststand geöffnet. LAYERLING_URL=${fixture.origin}. Zum Beenden dieses Chrome-Fenster schließen oder Strg+C drücken.`);
    await new Promise(resolve => {
      if (chrome.exitCode !== null || ws.readyState !== WebSocket.OPEN || demoStop.signal.aborted) return resolve();
      chrome.once('exit', resolve);
      ws.addEventListener('close', resolve, {once: true});
      demoStop.signal.addEventListener('abort', resolve, {once: true});
    });
  } else if (fixture.mcp) {
    await testMcp();
  } else {
  assert.equal(await evaluate('location.pathname'), '/cad.php');
  await waitFor("document.querySelector('.dashboard-legal')!==null",'Layerling footer');
  stage='school dashboard after a release';
  await evaluate("localStorage.setItem('layerling.lastSeenVersion', '1.142.0')");
  await navigate('/cad.php?mode=full');
  const whatsNewLink = "Array.from(document.querySelectorAll('.dashboard-legal a')).find(a => /^(What is new|Was ist neu)\\?$/.test(a.textContent.trim()))";
  await waitFor(whatsNewLink + " !== undefined", 'manual release notes link');
  assert.equal(await evaluate("document.querySelector('.dashboard-welcome-frame, .dashboard-legal a[href=\"#welcome\"], .whats-new') === null"), true);
  assert.equal(await evaluate("document.querySelector('link[rel=manifest]') === null"), true);
  assert.deepEqual(manifestRequests, []);
  await evaluate(whatsNewLink + ".click()");
  await waitFor("document.querySelector('.whats-new') !== null", 'release notes open on request');
  await evaluate("document.querySelector('.whats-new-close').click()");
  await waitFor("document.querySelector('.whats-new') === null", 'release notes closed');
  assert.equal(await evaluate("document.querySelector('.support-nudge, .dashboard-legal-sponsor')===null"),true,'upstream support prompts disabled');
  assert.equal(await evaluate("document.querySelector('#sso-cad-footer > details').open"),false,'SSO menu starts collapsed');
  const menuSummary = "document.querySelector('#sso-cad-footer > details > summary')";
  const studentLabel = 'Änne Muster (5a, 7c)';
  assert.equal(await evaluate(menuSummary+".textContent"),studentLabel);
  assert.equal(await evaluate(menuSummary+".classList.contains('sso-cad-foreign-account')"),false);
  assert.equal(await evaluate("document.querySelector('.dashboard-shell').getBoundingClientRect().bottom <= document.getElementById('sso-cad-footer').getBoundingClientRect().top"),true,'closed footer does not cover the dashboard');
  await command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
  await openFooter();
  assert.equal(await evaluate("document.getElementById('sso-cad-nav').getBoundingClientRect().right <= innerWidth"),true,'open menu fits a narrow viewport');
  await evaluate("document.querySelector('#sso-cad-footer > details > summary').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))");
  assert.equal(await evaluate("document.querySelector('#sso-cad-footer > details').open"),false,'Escape closes the menu');
  await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  assert.equal(await evaluate("localStorage.getItem('sso-unscoped-probe')"),null,'unscoped legacy cache not imported');
  stage='offline worker check';assert.equal(await evaluate("navigator.serviceWorker.controller===null && (await navigator.serviceWorker.getRegistrations()).length===0"),true,'no offline worker');
  stage='listing';assert.equal(await evaluate("(await fetch('/store.php')).status"),200,'authenticated adapter listing');
  assert.equal(await evaluate("(await fetch('/store.php?_sso_owner="+fixture.otherOwner+"').then(()=>false,()=>true))"),true,'foreign owner refused by own-only bridge');
  // Verify real browser cache partitioning with an unscoped legacy value left outside the facade.
  await evaluate("(localStorage.setItem('sso-test','owner-A'),sessionStorage.setItem('sso-test','A-tab'))");
  stage='create button';await waitFor("Array.from(document.querySelectorAll('button')).some(b=>/create new 3d design|neuen 3d.*(?:anlegen|erstellen)/i.test(b.textContent))",'create control');
  await evaluate("Array.from(document.querySelectorAll('button')).find(b=>/create new 3d design|neuen 3d.*(?:anlegen|erstellen)/i.test(b.textContent)).click()");
  stage='create/save';await waitFor("location.search.includes('editor=1')",'editor opened');
  await waitFor("document.querySelector('.editor-body')!==null",'editor work area');
  assert.equal(await evaluate("document.querySelector('.editor-body').getBoundingClientRect().bottom <= document.getElementById('sso-cad-footer').getBoundingClientRect().top"),true,'closed footer does not cover the work area');
  await waitFor("(await (await fetch('/store.php')).json()).projects?.length===1",'new project actually saved');
  stage='read created';const created=await evaluate("(await (await fetch('/store.php')).json()).projects[0]");
  assert.ok(created.revision,'server revision');
  stage='add geometry';
  await addBox(0.52);
  await waitFor("(await (await fetch('/store.php')).json()).projects[0].revision!=="+JSON.stringify(created.revision),'geometry saved with a new revision');

  stage='STEP export under the document CSP';
  const stepText = await evaluate(`(async () => {
    const module = new URL(${JSON.stringify(fixture.occtIndex)}, location.href);
    const {OcctKernel} = await import(module.href);
    const kernel = await OcctKernel.init({wasm:new URL('occt-wasm.wasm',module).href});
    const shape = kernel.makeBox(10, 20, 30);
    try { return kernel.exportStep(shape); }
    finally { kernel.release(shape); }
  })()`);
  assert.match(stepText, /^ISO-10303-21;/);
  assert.match(stepText, /MANIFOLD_SOLID_BREP/);
  stage='STEP download through the editor';
  await command('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:profile});
  await evaluate("document.querySelector('button[aria-label=\"Exportieren\"],button[aria-label=\"Export\"]').click()");
  await waitFor("document.querySelector('button[role=radio][aria-label^=\"STEP:\"]')!==null",'STEP format control');
  await evaluate("document.querySelector('button[role=radio][aria-label^=\"STEP:\"]').click()");
  await evaluate("document.getElementById('export-file-name').focus()");
  await enterSearch('sso-csp-step');
  await evaluate("document.querySelector('.export-primary-button').click()");
  const downloaded = await readDownload('sso-csp-step.step');
  assert.match(downloaded, /^ISO-10303-21;/);
  assert.match(downloaded, /MANIFOLD_SOLID_BREP/);

  stage='SVG silhouette download through the editor';
  await waitFor("document.querySelector('.export-action-panel')===null",'STEP panel closed');
  await evaluate("document.querySelector('button[aria-label=\"Exportieren\"],button[aria-label=\"Export\"]').click()");
  await waitFor("document.querySelector('button[role=radio][aria-label^=\"SVG:\"]')!==null",'SVG format control');
  await evaluate("document.querySelector('button[role=radio][aria-label^=\"SVG:\"]').click()");
  assert.equal(await evaluate("document.querySelector('select:has(option[value=silhouette])').value"), 'silhouette');
  await evaluate("document.getElementById('export-file-name').focus()");
  await enterSearch('sso-csp-silhouette');
  await evaluate("document.querySelector('.export-primary-button').click()");
  const silhouette = await readDownload('sso-csp-silhouette.svg');
  assert.match(silhouette, /<desc>Top-view vector projection exported by Layerling<\/desc>/);
  assert.match(silhouette, /<path[^>]* d="M/);

  // A complete reload must reopen the original CAD project through its scoped IndexedDB cache.
  stage='reload';const editorPath=await evaluate('location.pathname+location.search');assert.equal(editorPath.split('?')[0],'/cad.php');
  await command('Page.reload',{ignoreCache:true});
  await waitFor("document.readyState==='complete' && document.documentElement.dataset.ssoCad==='ready'",'reload online');
  await waitFor("document.querySelector('.three-workplane-host canvas')!==null",'CAD canvas after reopening');
  assert.equal(await evaluate("localStorage.getItem('sso-test')"),'owner-A');
  const saved=await evaluate("(await (await fetch('/store.php')).json()).projects[0]");assert.equal(saved.fileName,created.fileName);
  stage='reopen from server without browser copy';
  await command('Page.navigate',{url:'about:blank'});
  await waitFor("location.href==='about:blank' && document.readyState==='complete'",'leave editor before clearing synthetic cache');
  await command('Storage.clearDataForOrigin',{origin:fixture.origin,storageTypes:'indexeddb,local_storage'});
  await navigate('/cad.php');
  assert.equal(await evaluate("localStorage.getItem('sso-test')"),null,'browser copies actually removed');
  await waitFor("document.querySelector('.shared-project-card .project-card-open')!==null",'server design card');
  await evaluate("document.querySelector('.shared-project-card .project-card-open').click()");
  await waitFor("location.search.includes('editor=1') && document.querySelector('.three-workplane-host canvas')!==null",'server design reopened');
  await evaluate("localStorage.setItem('sso-test','owner-A')");
  const screenshot=await command('Page.captureScreenshot',{format:'png'});await writeFile('/private/tmp/sso-layerling-cad-own.png',Buffer.from(screenshot.data,'base64'));
  stage='nested student fixture';
  const sourceQuery = '/store.php?' + new URLSearchParams({fileName:saved.fileName});
  const originalBytes = await evaluate("Array.from(new Uint8Array(await (await fetch("+JSON.stringify(sourceQuery)+")).arrayBuffer()))");
  assert.equal(await evaluate("(await fetch('/store.php?folder=Werkstatt',{method:'POST'})).status"),201);
  const moveQuery = sourceQuery + '&moveTo=Werkstatt';
  assert.equal(await evaluate("(await fetch("+JSON.stringify(moveQuery)+",{method:'POST',headers:{'If-Match':"+JSON.stringify('"'+saved.revision+'"')+"}})).status"),200);
  // Another login in this same browser must freeze the old tab before any save can go out.
  stage='switch login';await cookies(fixture.otherCookies);
  assert.equal(await evaluate("fetch('/store.php').then(()=>false,()=>true)"),true,'changed session rejected');
  assert.equal(await evaluate("document.documentElement.dataset.ssoCad"),'locked');
  await navigate('/cad.php');
  assert.equal(await evaluate("localStorage.getItem('sso-test')"),null,'no previous account cache');
  assert.equal(await evaluate("(await (await fetch('/store.php')).json()).projects.length"),0,'no previous account file');
  const dbs=await evaluate("(await indexedDB.databases()).every(d=>!d.name.includes('sso.cad.v1.'))");assert.equal(dbs,true,'only current account logical database names');
  stage='failed create stays on dashboard';
  await command('Fetch.enable',{patterns:[{urlPattern:fixture.origin+'/store.php*',requestStage:'Request'}]});
  await waitFor("Array.from(document.querySelectorAll('button')).some(b=>/create new 3d design|neuen 3d.*(?:anlegen|erstellen)/i.test(b.textContent))",'create control for failure');
  await evaluate("Array.from(document.querySelectorAll('button')).find(b=>/create new 3d design|neuen 3d.*(?:anlegen|erstellen)/i.test(b.textContent)).click()");
  await waitFor("document.body.textContent.includes('fixture upload failure')",'upload failure shown');
  assert.equal(await evaluate("location.search.includes('editor=1')"),false,'failed server create does not silently open local editor');
  assert.equal(await evaluate("(await (await fetch('/store.php')).json()).projects.length"),0,'failed file not saved');
  await command('Fetch.disable');
  assert.equal(await evaluate("(await fetch("+JSON.stringify(sourceQuery)+",{method:'POST',headers:{'Content-Type':'application/vnd.layerling.project+zip'},body:new Uint8Array("+JSON.stringify(originalBytes)+")})).status"),201,'same filename in a different student area');
  stage='offline gate';
  await command('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  await evaluate("fetch('/store.php').catch(()=>null)");
  await waitFor("document.documentElement.dataset.ssoCad==='locked'",'offline blocks editor');
  await command('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  assert.equal(await evaluate("document.documentElement.dataset.ssoCad"),'locked','online does not silently unlock');
  await navigate('/cad.php');
  // Simulate logout by removing the native cookie, then require an explicit locked state.
  await command('Network.deleteCookies',{name:'SSO_LAYERLING_SESSION',url:fixture.origin+'/'});
  assert.equal(await evaluate("fetch('/store.php').then(()=>false,()=>true)"),true);
  assert.equal(await evaluate("document.documentElement.dataset.ssoCad"),'locked');
  stage='maker owner selection';
  await cookies(fixture.makerCookies);
  await navigate('/cad.php');
  assert.equal(await evaluate(menuSummary+".textContent"),'Klara Betreuung');
  await evaluate("localStorage.setItem('sso-test','maker-own')");
  await focusDesignSearch();
  await enterSearch('kein solcher Entwurf');
  await waitFor("/Nothing found|Nichts gefunden/.test(document.querySelector('.project-empty[role=status]')?.textContent)",'true empty search');
  await openAccounts();
  const ownerOptions = "Array.from(document.querySelectorAll('#sso-cad-accounts li:not([hidden]) a'), link=>[new URL(link.href).searchParams.get('owner'),link.textContent])";
  assert.deepEqual((await evaluate(ownerOptions)).map(([id])=>id).sort(), [null,fixture.owner,fixture.otherOwner].sort());
  assert.equal((await evaluate(ownerOptions)).find(([id])=>id===null)[1],'Klara Betreuung');
  await enterSearch('6B');
  assert.deepEqual(await evaluate(ownerOptions), [[fixture.unnamedOwner,'Nutzer '+fixture.unnamedOwner.slice(0,8)+' (6b)']]);
  await enterSearch('kein solcher Name');
  assert.equal(await evaluate(ownerOptions+".length"),0);
  assert.equal(await evaluate("document.querySelector('#sso-cad-accounts [role=status]').hidden"),false);
  await enterSearch('ÄNNE');
  assert.deepEqual((await evaluate(ownerOptions)).sort(), [
    [fixture.owner,studentLabel+' · '+fixture.owner.slice(0,8)],
    [fixture.otherOwner,studentLabel+' · '+fixture.otherOwner.slice(0,8)]
  ].sort(),'only authorized matching owners, with distinct labels for identical names');
  assert.equal(await evaluate("Array.from(document.querySelectorAll('#sso-cad-accounts a')).some(link=>link.href.includes("+JSON.stringify(fixture.teacherOwner)+"))"),false);
  assert.equal(await evaluate("document.querySelector('#sso-cad-nav a[href^=\"/konto\"], #sso-cad-nav a[href^=\"/files\"]')===null"),true);
  await evaluate("document.querySelector('#sso-cad-accounts a[href=\"/cad.php?owner="+fixture.owner+"\"]').click()");
  await waitFor("new URLSearchParams(location.search).get('owner')==="+JSON.stringify(fixture.owner)+" && document.documentElement.dataset.ssoCad==='ready'",'selected owner navigation');
  const selectedLabel = studentLabel+' · '+fixture.owner.slice(0,8);
  assert.equal(await evaluate("document.querySelector('#sso-cad-nav strong').textContent"),'Aktives Konto: '+selectedLabel);
  assert.equal(await evaluate(menuSummary+".textContent"),'Fremdes Konto: '+selectedLabel);
  assert.equal(await evaluate(menuSummary+".classList.contains('sso-cad-foreign-account')"),true);
  assert.equal(await evaluate("document.documentElement.dataset.ssoCanDelete"),'false');
  assert.equal(await evaluate("localStorage.getItem('sso-test')"),null,'foreign cache separated from both users');
  await evaluate("localStorage.setItem('sso-test','maker-student')");
  assert.equal(await evaluate("(await (await fetch('/store.php?settings=default')).json()).enabled"),false);
  stage='student design search';
  await focusDesignSearch();
  await enterSearch('kein solcher Entwurf');
  await waitFor("/Only the first few|nur die ersten/.test(document.querySelector('.project-empty[role=status]')?.textContent)",'truncated search with no matches');
  await command('Fetch.enable',{patterns:[{urlPattern:fixture.origin+'/store.php*',requestStage:'Request'}]});
  await enterSearch('fixture-failure');
  await waitFor("/Could not load the designs|Entwürfe auf dem Server konnten nicht geladen/.test(document.querySelector('.project-empty[role=status]')?.textContent)",'failed search has its own status');
  await command('Fetch.disable');
  const searchTerm = saved.name;
  await enterSearch(searchTerm);
  await waitFor("document.querySelector('.shared-project-card .project-card-folder')?.textContent.includes('Werkstatt')",'search result includes nested folder');
  await waitFor("/Only the first few|nur die ersten/.test(document.querySelector('.store-search-line')?.textContent)",'truncated search with matches');
  await waitFor("document.querySelector('.shared-project-card .project-menu-trigger')!==null",'student project menu');
  await evaluate("document.querySelector('.shared-project-card .project-menu-trigger').click()");
  await waitFor("document.querySelector('.shared-project-card .project-card-menu .delete')!==null",'student delete control mounted');
  assert.equal(await evaluate("getComputedStyle(document.querySelector('.shared-project-card .project-card-menu .delete')).display"),'none');
  const folderListing = "(await (await fetch('/store.php?path=Werkstatt')).json()).projects";
  const foreign = await evaluate(folderListing+"[0]");
  const remove = sourceQuery + '&path=Werkstatt';
  const deletion = "fetch("+JSON.stringify(remove)+",{method:'DELETE',headers:{'If-Match':"+JSON.stringify('"'+foreign.revision+'"')+"}})";
  assert.equal(await evaluate("(await "+deletion+").status"),403);
  assert.equal(await evaluate("document.documentElement.dataset.ssoCad"),'ready','denied delete does not lock allowed edits');
  await evaluate("document.querySelector('.shared-project-card .project-card-open').click()");
  await waitFor("location.search.includes('editor=1') && document.querySelector('.three-workplane-host canvas')!==null",'student design opened');
  assert.equal(await evaluate("new URLSearchParams(location.search).get('owner')"),fixture.owner);
  stage='maker edit';
  await addBox(0.36);
  await waitFor(folderListing+"[0].revision!=="+JSON.stringify(foreign.revision),'student edit saved');
  await command('Page.reload',{ignoreCache:true});
  await waitFor("document.readyState==='complete' && document.documentElement.dataset.ssoCad==='ready' && document.querySelector('.three-workplane-host canvas')!==null",'student edit reopens after reload');
  assert.equal(await evaluate("localStorage.getItem('sso-test')"),'maker-student');
  await navigate('/cad.php?owner='+fixture.owner);
  await focusDesignSearch();
  await enterSearch(searchTerm);
  await waitFor("document.querySelector('.shared-project-card .project-card-folder')?.textContent.includes('Werkstatt')",'saved project is found again');
  await evaluate("document.querySelector('.shared-project-card .project-card-open').click()");
  await waitFor("location.search.includes('editor=1') && document.querySelector('.three-workplane-host canvas')!==null",'saved student design reopened from server search');
  await openAccounts();
  await evaluate("document.querySelector('#sso-cad-accounts a[href=\"/cad.php\"]').click()");
  await waitFor("location.search==='' && document.documentElement.dataset.ssoCad==='ready'",'own area shortcut');
  assert.equal(await evaluate("localStorage.getItem('sso-test')"),'maker-own');
  assert.equal(await evaluate("(await (await fetch('/store.php')).json()).projects.length"),0);
  stage='admin deletion';
  await cookies(fixture.adminCookies);
  await navigate('/cad.php?owner='+fixture.owner);
  assert.equal(await evaluate("document.documentElement.dataset.ssoCanDelete"),'true');
  assert.equal(await evaluate("localStorage.getItem('sso-test')"),null,'admin cache separate from supervision cache');
  await focusDesignSearch();
  await enterSearch(searchTerm);
  await waitFor("document.querySelector('.shared-project-card .project-menu-trigger')!==null",'admin project menu');
  await evaluate("document.querySelector('.shared-project-card .project-menu-trigger').click()");
  await waitFor("document.querySelector('.shared-project-card .project-card-menu .delete')?.getClientRects().length>0",'admin delete visible');
  // Copy the real project before exercising admin deletion so the supervised original remains verifiable.
  const copyQuery = remove + '&copyTo=admin-test-copy.lyl';
  const latest = await evaluate(folderListing+"[0]");
  assert.equal(await evaluate("(await fetch("+JSON.stringify(copyQuery)+",{method:'POST',headers:{'If-Match':"+JSON.stringify('"'+latest.revision+'"')+"}})).status"),201);
  const copy = await evaluate(folderListing+".find(p=>p.fileName==='admin-test-copy.lyl')");
  assert.ok(copy);
  const deleteCopy = '/store.php?' + new URLSearchParams({fileName:copy.fileName,path:'Werkstatt'});
  assert.equal(await evaluate("(await fetch("+JSON.stringify(deleteCopy)+",{method:'DELETE',headers:{'If-Match':"+JSON.stringify('"'+copy.revision+'"')+"}})).status"),200);

  stage='publish classroom template';
  const templateFile = join(profile, 'Unterricht.lyl');
  await writeFile(templateFile, Buffer.from(originalBytes));
  await cookies(fixture.teacherCookies);
  await command('Page.navigate',{url:fixture.origin+'/vorlagen.php'});
  await waitFor("document.querySelector('#publish-template input[type=file]')!==null",'template publish form');
  await waitFor("document.querySelector('.sso-brand img')?.naturalWidth > 0", 'Layerling logo loads on the template page');
  await checkNarrowPage();
  const instructions = 'Ergänze den Entwurf.\n\nhttps://material.example.invalid/' + 'konstruktionswerkstatt'.repeat(12);
  await evaluate(`(() => {
    document.querySelector('[name=title]').value = 'CAD Aufgabe';
    document.querySelector('[name=instructions]').value = ${JSON.stringify(instructions)};
    document.querySelector('input[value="cad-class"]').checked = true;
  })()`);
  const {root: {nodeId: documentId}} = await command('DOM.getDocument');
  const {nodeId: uploadField} = await command('DOM.querySelector',{nodeId:documentId,selector:'#publish-template input[type=file]'});
  await command('DOM.setFileInputFiles',{nodeId:uploadField,files:[templateFile]});
  await evaluate("document.querySelector('#publish-template').requestSubmit()");
  await waitFor("document.querySelector('[data-withdraw-template]')!==null",'published template in teacher catalogue');

  stage='students copy and edit independently';
  const taskList = "(await (await fetch('/store.php')).json()).projects.find(p=>p.name==='CAD Aufgabe')";
  let templateStudent = 0;
  for (const [studentCookies, offsets] of [[fixture.cookies, [0.36]], [fixture.otherCookies, [0.36, 0.65]]]) {
    stage = 'students copy and edit independently: student ' + (++templateStudent);
    await cookies(studentCookies);
    await navigate('/cad.php');
    await openFooter();
    await evaluate("document.querySelector('#sso-cad-nav a[href=\"/vorlagen.php\"]').click()");
    await waitFor("document.querySelector('[data-copy-template]')!==null",'student sees classroom template');
    await checkNarrowPage();
    const copyForm = "document.querySelector('[data-copy-template]')";
    const copyStatus = copyForm + ".querySelector('[data-template-status]')";
    for (const feedback of ['liegt jetzt', 'bereits belegt']) {
      await evaluate(`(() => {
        const button = ${copyForm}.querySelector('button');
        button.scrollIntoView({block:'end'});
        button.focus();
        button.click();
      })()`);
      await waitFor(copyStatus + '.textContent.includes(' + JSON.stringify(feedback) + ')', 'inline feedback: ' + feedback);
      assert.equal(await evaluate(`(() => {
        const rect = ${copyStatus}.getBoundingClientRect();
        return rect.top >= 0 && rect.bottom <= innerHeight;
      })()`), true, 'copy feedback remains visible');
    }
    await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await navigate('/cad.php');
    await focusDesignSearch();
    await enterSearch('CAD Aufgabe');
    await waitFor("document.querySelector('.shared-project-card .project-card-title')?.textContent==='CAD Aufgabe'",'copied project in personal store');
    await evaluate("document.querySelector('.shared-project-card .project-card-open').click()");
    await waitFor("location.search.includes('editor=1') && document.querySelector('.three-workplane-host canvas')!==null",'own copy opens in editor');
    for (const offset of offsets) {
      const previous = await evaluate(taskList);
      await addBox(offset);
      await waitFor(taskList+".revision!=="+JSON.stringify(previous.revision),'edit saved to own copy');
    }
    await command('Page.reload',{ignoreCache:true});
    await waitFor("document.readyState==='complete' && document.documentElement.dataset.ssoCad==='ready' && document.querySelector('.three-workplane-host canvas')!==null",'own edited copy reopens');
  }

  stage = 'file page at narrow widths';
  await command('Page.navigate', {url:fixture.origin + '/files/'});
  await waitFor("document.querySelector('#owner:not(:disabled)') !== null", 'file list loaded');
  await waitFor("document.querySelector('.sso-brand img')?.naturalWidth > 0", 'Layerling logo loads on the file page');
  await checkNarrowPage();
  let path = '';
  for (const name of ['Konstruktionswerkstatt', 'Abschlussprojekt'].map(word => word.repeat(3))) {
    await evaluate(`(() => {
      const input = document.getElementById('folderName');
      input.value = ${JSON.stringify(name)};
      input.form.requestSubmit();
    })()`);
    const open = "document.querySelector('#entries button[aria-label=" + JSON.stringify('Öffnen – Ordner ' + name) + "]')";
    await waitFor(open + ' !== null', 'new folder is listed');
    await evaluate(`(() => { const button = ${open}; button.focus(); button.click(); })()`);
    path += '/' + name;
    await waitFor("document.querySelector('#path').textContent === " + JSON.stringify(path), 'new folder path is shown');
    assert.equal(await evaluate("document.activeElement.id"), 'folder-heading', 'focus follows folder navigation');
    await checkNarrowPage();
  }
  await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await navigate('/cad.php');

  stage='logout from SSO footer';
  await openFooter();
  await evaluate("document.querySelector('#sso-cad-nav button[type=submit]').click()");
  await waitFor("location.pathname==='/index.php' && document.querySelector('form[action=\"/auth/start.php\"]')!==null", 'footer logout returns to manual IServ login');
  stage = 'permissions page at narrow widths';
  await testPermissions();
  stage = 'account and manual login at narrow widths';
  await testAccount();
  assert.deepEqual(errors,[],'no uncaught script errors');
  process.stdout.write('CAD_BROWSER_OK: geometry save/reopen, filtered owner selection, nested project search, search errors and truncation, rights, cache isolation and logout\n');
  }
}catch(error){
  let state={};if(ws?.readyState===1)try{state=await evaluate("({url:location.pathname+location.search,templateStatus:Array.from(document.querySelectorAll('[data-template-status]')).map(status=>status.textContent).filter(Boolean),templateNames:Array.from(document.querySelectorAll('[data-copy-template] input[name=name]')).map(input=>input.value),state:document.documentElement.dataset.ssoCad,reason:document.getElementById('sso-cad-status')?.textContent,buttons:Array.from(document.querySelectorAll('button')).slice(0,18).map(b=>b.textContent.slice(0,70)),errors:"+JSON.stringify(errors)+"})");}catch{}
  if(!fixture.mcp && !fixture.demo && ws?.readyState===1)try{const shot=await command('Page.captureScreenshot',{format:'png'});await writeFile('/private/tmp/sso-layerling-cad-failure.png',Buffer.from(shot.data,'base64'));}catch{}
  process.stderr.write(stage+': '+error.message+'\n'+JSON.stringify(state)+'\n');process.exitCode=1;
}finally{
  if(ws?.readyState===1){try{await command('Browser.close');}catch{}ws.close();}
  chrome.kill('SIGTERM');await new Promise(resolve=>{if(chrome.exitCode!==null)resolve();else{chrome.once('exit',resolve);setTimeout(resolve,3000);}});
  await rm(profile,{recursive:true,force:true,maxRetries:3,retryDelay:100});
}
