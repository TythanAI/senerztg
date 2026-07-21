# AI SDK `smoothStream()` ReDoS / event-loop DoS — PoC

Verified finding for the **Vercel Open Source** bug bounty program.
Full write-up: [`REPORT.md`](./REPORT.md).

**TL;DR:** `smoothStream()` (default `chunking: 'word'`) uses `/\S+\s+/m` with `exec()` (no `g`
flag) against the whole accumulated buffer on every streamed model token. A model response
containing a long run of contiguous non-whitespace characters causes quadratic-per-scan /
~cubic-aggregate backtracking that consumes tens of seconds of server CPU and can fully freeze the
Node.js event loop, denying service to all concurrent users.

Affected: `ai@7.0.34` (latest) and the `ai-v5` / `ai-v6` / `canary` lines.

## Run it (no API keys, no network)

```bash
npm install ai          # ai@7.0.34+
node poc.js             # end-to-end through streamText({ experimental_transform: smoothStream() })
node poc-transform.js   # isolates the transform; includes a whitespace "control" case
node single-exec-benchmark.js   # quadratic cost of one exec() on N non-whitespace chars
```

## Expected output (Node 22, ai@7.0.34)

`poc.js` (end-to-end):

```
2000 non-whitespace chars -> event loop busy ~1.4s
4000 non-whitespace chars -> event loop busy ~7.1s
6000 non-whitespace chars -> event loop busy ~21.6s
```

`poc-transform.js`:

```
word mode, 8000 chars, ws-every-8   time=0.03s   (control: normal operation)
word mode, 2000 non-ws chars        time~0.8s
word mode, 4000 non-ws chars        time~5.9s
word mode, 6000 non-ws chars        time~19.6s
line mode, 4000 non-newline chars   time=0.02s   (line mode NOT affected)
```

`single-exec-benchmark.js` (a single `exec()`, full event-loop freeze):

```
N=50000:  ~2.7s
N=100000: ~10.7s
N=200000: ~43s
```

## Files

- `REPORT.md` — HackerOne-format vulnerability report (root cause, repro, impact, CVSS, fix).
- `poc.js` — end-to-end PoC via the real `streamText()` pipeline + bundled mock model.
- `poc-transform.js` — drives the real `smoothStream()` transform directly; includes control + `line` mode.
- `single-exec-benchmark.js` — quadratic cost of a single `/\S+\s+/m` `exec()`.
