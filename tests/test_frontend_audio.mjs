import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(
  new URL("../frontend/src/audio.js", import.meta.url),
  "utf8",
);
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { Audio } = await import(moduleUrl);

class FakeNode {
  constructor() {
    this.gain = { value: 1 };
    this.pan = { value: 0 };
  }

  connect(next) {
    return next;
  }
}

class FakeSource extends FakeNode {
  constructor() {
    super();
    this.started = 0;
    this.stops = 0;
    this.onended = null;
  }

  start() {
    this.started += 1;
  }

  stop() {
    this.stops += 1;
  }
}

class FakeContext {
  constructor() {
    this.sources = [];
    this.destination = new FakeNode();
    this.state = "running";
  }

  createBufferSource() {
    const source = new FakeSource();
    this.sources.push(source);
    return source;
  }

  createGain() {
    return new FakeNode();
  }

  createStereoPanner() {
    return new FakeNode();
  }

  async decodeAudioData(bytes) {
    return { bytes };
  }
}

function install(fetchImpl) {
  globalThis.window = { AudioContext: FakeContext };
  globalThis.fetch = fetchImpl;
}

const okFetch = async () => ({ ok: true, arrayBuffer: async () => new ArrayBuffer(1) });

test("a new cue on the same channel replaces the running one", async () => {
  // Native backends replace on channel reuse; stacking here made every music change
  // pile another loop on top of the last.
  install(okFetch);
  const audio = new Audio();
  await audio.play({ file: "a.ogg", channel: "music", loop: true });
  await audio.play({ file: "b.ogg", channel: "music", loop: true });
  const [first, second] = audio.ctx.sources;
  assert.equal(first.stops, 1);
  assert.equal(second.stops, 0);
  assert.equal(second.started, 1);
});

test("distinct channels overlap untouched", async () => {
  install(okFetch);
  const audio = new Audio();
  await audio.play({ file: "a.ogg", channel: "steps" });
  await audio.play({ file: "b.ogg", channel: "ambience" });
  const [first, second] = audio.ctx.sources;
  assert.equal(first.stops, 0);
  assert.equal(second.stops, 0);
});

test("a slow-loading older cue never replaces the newer one", async () => {
  // play() awaits the fetch+decode; without a generation check the FIRST cue's late
  // completion would stop and replace the second, ending on the wrong sound.
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  let calls = 0;
  install(async () => {
    calls += 1;
    if (calls === 1) await gate;  // the first file loads slowly
    return { ok: true, arrayBuffer: async () => new ArrayBuffer(1) };
  });
  const audio = new Audio();
  const slow = audio.play({ file: "slow.ogg", channel: "sound" });
  const fast = audio.play({ file: "fast.ogg", channel: "sound" });
  await fast;
  release();
  await slow;
  assert.equal(audio.ctx.sources.length, 1);  // the stale cue was dropped, not started
  assert.equal(audio.ctx.sources[0].stops, 0);
});

test("stop silences only the named channel", async () => {
  install(okFetch);
  const audio = new Audio();
  await audio.play({ file: "a.ogg", channel: "music", loop: true });
  await audio.play({ file: "b.ogg", channel: "steps" });
  audio.stop("music");
  const [music, steps] = audio.ctx.sources;
  assert.equal(music.stops, 1);
  assert.equal(steps.stops, 0);
});
