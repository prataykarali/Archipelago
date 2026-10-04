import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
const source = await readFile(new URL('../../host_inference/ui/js/chat-transport.js', import.meta.url), 'utf8');
const { ChatTransport, readChatResponse } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const HEADER = '{"routing":"GRAPH","anchor_concept":{"id":"rag"}}[STREAM_START]';

function decode(chunks, mime = 'text/plain') {
    const parser = new ChatTransport(mime);
    return [...chunks.flatMap(chunk => parser.push(chunk)), ...parser.finish()];
}
const text = events => events.filter(e => e.type === 'text').map(e => e.value).join('');

test('all stream-start split positions preserve metadata and Unicode answer', () => {
    const raw = HEADER + 'Real answer π.';
    for (let i = 1; i < raw.length; i++) {
        const events = decode([raw.slice(0, i), raw.slice(i)]);
        assert.equal(events[0].type, 'metadata');
        assert.equal(text(events), 'Real answer π.');
    }
});
test('all rewrite/final boundary positions preserve the complete final frame', () => {
    const raw = HEADER + 'Draft[MODEL_REWRITE]New draft[STREAM_DONE]Complete final answer.';
    for (let i = 1; i < raw.length; i++) {
        const events = decode([raw.slice(0, i), raw.slice(i)]);
        assert.equal(events.at(-1).value, '[STREAM_DONE]Complete final answer.');
        assert.equal(text(events), 'Draft[MODEL_REWRITE]New draft[STREAM_DONE]Complete final answer.');
    }
});
test('one-character chunks never leak split control markers', () => {
    const events = decode((HEADER + 'Draft[CLEAN]Final').split(''));
    assert.equal(events.at(-1).value, '[STREAM_DONE]Final');
});
test('JSON error is a readable failure, not answer content', () => {
    assert.throws(() => decode(['{"error":"<img onerror=evil()>"}'], 'application/json'), /unavailable/);
});
test('missing or malformed metadata separator fails closed', () => {
    for (const raw of ['{"routing":"GRAPH"}', '{"anchor_concept":', '{"routing":[STREAM_START]answer', '[]' + '[STREAM_START]answer']) {
        assert.throws(() => decode([raw]), /incomplete or invalid/);
    }
});
test('empty transport is an explicit failure', () => {
    assert.throws(() => decode(['']), /empty/);
    assert.throws(() => decode([HEADER]), /empty/);
});
test('header cap prevents unlimited unframed metadata', () => {
    assert.throws(() => decode(['x'.repeat(128 * 1024 + 1)]), /incomplete or invalid/);
});
test('JSON success envelopes extract only the answer', () => {
    assert.equal(text(decode(['{"text":"Hello","metadata":{"routing":"GREETING"}}'], 'application/json')), 'Hello');
});
test('intentional JSON/code answers are preserved', () => {
    assert.equal(text(decode([HEADER + '{"routing":"example code"}'])), '{"routing":"example code"}');
    assert.equal(text(decode(['{"total":3}'], 'application/json')), '{"total":3}');
    assert.equal(text(decode(['[1,2,3]'], 'application/json')), '[1,2,3]');
    assert.equal(text(decode([HEADER + '```json\n{"a":1}\n```'])), '```json\n{"a":1}\n```');
});
test('legacy plain-text answers stay readable', () => {
    assert.equal(text(decode(['Hello world.'])), 'Hello world.');
});
test('HTML and non-2xx responses do not enter answer rendering', async () => {
    assert.throws(() => decode(['<html>Login</html>'], 'text/html'), /incomplete/);
    await assert.rejects(async () => {
        for await (const event of readChatResponse(new Response('private upstream body', { status: 503 }))) assert.fail(event);
    }, /HTTP 503/);
});
test('UTF-8 decoder handles bytes split inside characters', async () => {
    const bytes = new TextEncoder().encode(HEADER + '你好 π.');
    const body = new ReadableStream({ start(controller) {
        for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
        controller.close();
    }});
    const events = [];
    for await (const event of readChatResponse(new Response(body, { headers: {'content-type':'text/plain'} }))) events.push(event);
    assert.equal(text(events), '你好 π.');
});