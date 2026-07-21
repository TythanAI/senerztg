'use strict';
// End-to-end PoC through the REAL streamText() pipeline, exactly as documented:
//   streamText({ model, experimental_transform: smoothStream() })
// A mock model streams a long contiguous non-whitespace assistant message
// (as a real model does when asked to echo a long token / base64 / "aaaa...").
const { streamText, smoothStream } = require('ai');
const { MockLanguageModelV4, simulateReadableStream } = require('ai/test');

function makeModel(total, delta) {
  const parts = [{ type: 'text-start', id: '0' }];
  for (let i = 0; i < total; i += delta) {
    parts.push({ type: 'text-delta', id: '0', delta: 'a'.repeat(Math.min(delta, total - i)) });
  }
  parts.push({ type: 'text-end', id: '0' });
  parts.push({ type: 'finish', finishReason: 'stop', usage: { inputTokens: 1, outputTokens: total, totalTokens: total + 1 } });
  return new MockLanguageModelV4({
    doStream: async () => ({ stream: simulateReadableStream({ chunks: parts }) }),
  });
}

async function run(total, delta) {
  let ticks = 0, maxGap = 0, last = Date.now();
  const hb = setInterval(() => { const now = Date.now(); maxGap = Math.max(maxGap, now - last); last = now; ticks++; }, 100);
  const t = Date.now();
  const result = streamText({
    model: makeModel(total, delta),
    prompt: 'echo',
    experimental_transform: smoothStream({ delayInMs: null }), // default word chunking
  });
  // Drive the pipeline (server would do this to stream to the client).
  for await (const _ of result.textStream) { /* consume */ }
  const ms = Date.now() - t;
  clearInterval(hb);
  console.log(`streamText+smoothStream, ${String(total).padStart(5)} non-ws chars from model  => event loop blocked ${(ms/1000).toFixed(2)}s  (100ms-timer ticks during: ${ticks}, maxGap=${maxGap}ms)`);
}

(async () => {
  console.log('=== END-TO-END via streamText() — real ai@' + require('ai/package.json').version + ' ===');
  for (const L of [2000, 4000, 6000]) await run(L, 4);
})().catch(e => { console.error('ERROR:', e); process.exit(1); });
