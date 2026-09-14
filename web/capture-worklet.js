// AudioWorklet: downsample mic audio to 16 kHz mono float32 and post chunks.
class Capture extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const { targetRate, sourceRate } = options.processorOptions;
    this.ratio = sourceRate / targetRate;
    this.acc = [];
    this.accLen = 0;
    this.CHUNK = 2048; // ~128ms at 16kHz
  }
  process(inputs) {
    const ch = inputs[0][0];
    if (!ch) return true;
    // naive decimation with averaging
    const outLen = Math.floor(ch.length / this.ratio);
    const out = new Float32Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const start = Math.floor(i * this.ratio), end = Math.floor((i + 1) * this.ratio);
      let s = 0, n = 0;
      for (let j = start; j < end && j < ch.length; j++) { s += ch[j]; n++; }
      out[i] = n ? s / n : 0;
    }
    this.acc.push(out); this.accLen += out.length;
    if (this.accLen >= this.CHUNK) {
      const merged = new Float32Array(this.accLen);
      let o = 0;
      for (const a of this.acc) { merged.set(a, o); o += a.length; }
      this.port.postMessage(merged, [merged.buffer]);
      this.acc = []; this.accLen = 0;
    }
    return true;
  }
}
registerProcessor('capture', Capture);
