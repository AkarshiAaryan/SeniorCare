class VADProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this._threshold = (options && options.processorOptions && options.processorOptions.threshold) || 0.02;
    this._speechFrames = 0;
    this._silenceFrames = 0;
    this._speechConfirmFrames = (options && options.processorOptions && options.processorOptions.speechConfirmFrames) || 5; // ~125ms at 128 frame size
    this._silenceConfirmFrames = (options && options.processorOptions && options.processorOptions.silenceConfirmFrames) || 15; // ~375ms
    this._frameCount = 0;
  }

  _rms(input) {
    let sum = 0;
    for (let i = 0; i < input.length; i++) {
      const s = input[i];
      sum += s * s;
    }
    return Math.sqrt(sum / input.length);
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const channel = input[0];
    const rms = this._rms(channel);

    if (rms > this._threshold) {
      this._speechFrames += 1;
      this._silenceFrames = 0;
    } else {
      this._silenceFrames += 1;
      this._speechFrames = 0;
    }

    if (this._speechFrames >= this._speechConfirmFrames) {
      this.port.postMessage({ event: 'speech_detected', rms });
      this._speechFrames = 0;
    }

    if (this._silenceFrames >= this._silenceConfirmFrames) {
      this.port.postMessage({ event: 'silence_detected', rms });
      this._silenceFrames = 0;
    }

    return true;
  }
}

registerProcessor('vad-processor', VADProcessor);
