// Web Audio soundpack playback: per-channel gain/pan, overlapping one-shots, and
// looping music. Sound files are fetched from URLs the engine provides.

export class Audio {
  constructor(onError) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    this.ctx = new Ctx();
    this.buffers = new Map();
    this.channels = new Map();
    this.generations = new Map();  // per-channel cue counter; a stale load must not play
    this.onError = onError || (() => {});  // report load/decode failures, don't swallow them
  }

  _soundUrl(file) {
    // Sounds are served by the engine's static server under /sounds/.
    return "/sounds/" + file.split("/").map(encodeURIComponent).join("/");
  }

  async _load(file) {
    if (this.buffers.has(file)) return this.buffers.get(file);
    const url = this._soundUrl(file);
    const response = await fetch(url);
    if (!response.ok) throw new Error(`fetch ${response.status} for ${url}`);
    const bytes = await response.arrayBuffer();
    const buffer = await this.ctx.decodeAudioData(bytes);
    this.buffers.set(file, buffer);
    return buffer;
  }

  async play(message) {
    const channel = message.channel || "sound";
    const generation = (this.generations.get(channel) || 0) + 1;
    this.generations.set(channel, generation);
    let buffer;
    try {
      buffer = await this._load(message.file);
    } catch (e) {
      this.onError({ file: message.file, error: String((e && e.message) || e) });
      return;
    }
    if (this.generations.get(channel) !== generation) return;  // superseded while loading
    // The bus contract: a new cue on the SAME logical channel replaces the running one
    // (native packs rely on it, and every music change would otherwise stack another
    // loop forever). Overlap comes from distinct channels, which the shims mint freely.
    this.stop(channel);
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.loop = !!message.loop;
    const gain = this.ctx.createGain();
    gain.gain.value = message.gain ?? 1;
    const panner = this.ctx.createStereoPanner();
    panner.pan.value = message.pan ?? 0;
    source.connect(gain).connect(panner).connect(this.ctx.destination);
    source.start();
    this._track(channel, source);
  }

  stop(channel) {
    const sources = this.channels.get(channel);
    if (!sources) return;
    for (const source of sources) {
      try { source.stop(); } catch { /* already stopped */ }
    }
    sources.clear();
  }

  _track(channel, source) {
    if (!this.channels.has(channel)) this.channels.set(channel, new Set());
    const sources = this.channels.get(channel);
    sources.add(source);
    source.onended = () => sources.delete(source);
  }
}
