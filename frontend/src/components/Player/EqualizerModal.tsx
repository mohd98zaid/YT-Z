import React from 'react';
import { Sliders, X, RotateCcw, Power } from 'lucide-react';
import { usePlayerStore, EQ_FREQUENCIES, EQ_PRESETS } from '../../stores/usePlayerStore';

export const EqualizerModal: React.FC = () => {
  const {
    isEqualizerOpen,
    toggleEqualizer,
    eqEnabled,
    toggleEq,
    eqPreset,
    eqBands,
    setEqBand,
    setEqPreset,
  } = usePlayerStore();

  if (!isEqualizerOpen) return null;

  const formatFreq = (freq: number) => {
    return freq >= 1000 ? `${freq / 1000}k` : `${freq}`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-md select-none animate-fadeIn">
      <div className="bg-surface border border-border rounded-3xl p-6 w-full max-w-2xl shadow-2xl relative">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center border border-primary/20">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-foreground">10-Band Studio Equalizer</h3>
              <p className="text-xs text-foreground-muted">Hardware-accelerated Web Audio DSP</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Master EQ Power Toggle */}
            <button
              onClick={toggleEq}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
                eqEnabled
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-surface-elevated text-foreground-muted border-border'
              }`}
            >
              <Power className="w-3.5 h-3.5" />
              <span>{eqEnabled ? 'Active' : 'Bypassed'}</span>
            </button>

            {/* Close Button */}
            <button
              onClick={toggleEqualizer}
              className="p-2 rounded-full hover:bg-surface-elevated text-foreground-muted hover:text-foreground"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Preset Selector Chips */}
        <div className="mt-4 flex flex-wrap gap-2">
          {Object.keys(EQ_PRESETS).map((pName) => {
            const isSelected = eqPreset === pName;
            return (
              <button
                key={pName}
                onClick={() => setEqPreset(pName)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                  isSelected
                    ? 'bg-primary text-white shadow-md shadow-primary/20'
                    : 'bg-surface-elevated text-foreground-muted hover:text-foreground hover:bg-surface-elevated/80 border border-border'
                }`}
              >
                {pName}
              </button>
            );
          })}
        </div>

        {/* 10 Vertical Sliders */}
        <div className="mt-8 flex items-center justify-between px-2 h-52 bg-surface-elevated/50 border border-border/50 rounded-2xl p-4">
          {EQ_FREQUENCIES.map((freq, idx) => {
            const gain = eqBands[idx] || 0;
            return (
              <div key={freq} className="flex flex-col items-center justify-between h-full w-10">
                <span className="text-[10px] font-mono text-foreground-muted font-semibold">
                  {gain > 0 ? `+${gain}` : `${gain}`}
                </span>

                {/* Vertical Range Input */}
                <input
                  type="range"
                  min="-12"
                  max="12"
                  step="0.5"
                  value={gain}
                  disabled={!eqEnabled}
                  onChange={(e) => setEqBand(idx, parseFloat(e.target.value))}
                  className="h-32 -rotate-90 w-32 appearance-none bg-surface border border-border rounded-lg cursor-pointer accent-primary disabled:opacity-40"
                />

                <span className="text-[11px] font-bold text-foreground font-mono">
                  {formatFreq(freq)}
                </span>
              </div>
            );
          })}
        </div>

        {/* Footer controls */}
        <div className="mt-6 flex items-center justify-between text-xs text-foreground-muted">
          <span>Range: -12 dB to +12 dB</span>
          <button
            onClick={() => setEqPreset('Flat')}
            className="flex items-center gap-1.5 hover:text-foreground transition-colors font-medium"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset to Flat</span>
          </button>
        </div>
      </div>
    </div>
  );
};
