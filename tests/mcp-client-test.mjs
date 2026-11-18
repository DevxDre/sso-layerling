import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createServer } from 'node:http';
import { resolve } from 'node:path';
import { test } from 'node:test';

const client = resolve(process.argv[2] ?? 'build/sso-mcp-client/scripts/layerling-mcp-server.mjs');

test('stdio client waits for a hosted MCP result after HTTP 202', async (t) => {
  const commandId = 'a'.repeat(32);
  const received = [];
  const server = createServer(async (request, response) => {
    let body = '';
    for await (const chunk of request) body += chunk;
    received.push({ method: request.method, url: request.url,
      auth: request.headers.authorization, body: body ? JSON.parse(body) : null });
    response.setHeader('Content-Type', 'application/json');
    if (received.length < 3) {
      response.writeHead(202).end(JSON.stringify({commandId}));
    } else {
      response.end(JSON.stringify({ok: true, data: {shapeCount: 2}}));
    }
  });
  t.after(() => server.close());
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');

  const child = spawn(process.execPath, [client], {
    env: {...process.env, LAYERLING_URL: `http://127.0.0.1:${server.address().port}`,
      LAYERLING_MCP_TOKEN: 'synthetic-token', LAYERLING_MCP_OPEN_EDITOR: '0'},
    timeout: 5000,
  });
  const exited = once(child, 'close');
  child.stdin.end(JSON.stringify({jsonrpc: '2.0', id: 1, method: 'tools/call',
    params: {name: 'layerling_read_scene', arguments: {editorNumber: 12345}}}) + '\n');
  let result = '';
  for await (const chunk of child.stdout) result += chunk;
  assert.equal((await exited)[0], 0);
  assert.deepEqual(JSON.parse(JSON.parse(result).result.content[0].text), {shapeCount: 2});
  assert.deepEqual(received.map(({method, url}) => [method, url]), [
    ['POST', '/api/layerling-mcp'],
    ['GET', '/api/layerling-mcp?command=' + commandId],
    ['GET', '/api/layerling-mcp?command=' + commandId],
  ]);
  assert.ok(received.every(({auth}) => auth === 'Bearer synthetic-token'));
  assert.equal(received[0].body.action, 'get_scene');
  assert.equal(received[0].body.editorNumber, 12345);
});
