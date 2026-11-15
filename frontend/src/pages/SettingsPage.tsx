import React, { useState, useEffect } from 'react';
import { Palette, Volume2, Download, ShieldCheck, Check, Sparkles, Folder } from 'lucide-react';
import { THEME_PRESETS } from '../themes/presets';
import { useThemeStore } from '../stores/useThemeStore';
import { usePlayerStore } from '../stores/usePlayerStore';
import { api } from '../services/api';

export const SettingsPage: React.FC = () => {
  const { currentThemeId, setTheme } = useThemeStore();
  const { crossfadeSeconds, setCrossfade } = usePlayerStore();

  const [downloadDir, setDownloadDir] = useState('');
  const [concurrency, setConcurrency] = useState(3);
  const [sponsorblockEnabled, setSponsorblockEnabled] = useState(true);
  const [embedThumbnail, setEmbedThumbnail] = useState(true);
  const [embedMetadata, setEmbedMetadata] = useState(true);
  const [embedSubtitles, setEmbedSubtitles] = useState(false);
  const [savedToast, setSavedToast] = useState(false);

  useEffect(() => {
    api.getConfig().then((cfg) => {
      if (cfg) {
        setDownloadDir(cfg.download_dir || '');
        setConcurrency(cfg.concurrent_downloads || 3);
        setSponsorblockEnabled(cfg.sponsorblock_enabled !== false);
        setEmbedThumbnail(cfg.embed_thumbnail !== false);
        setEmbedMetadata(cfg.embed_metadata !== false);
        setEmbedSubtitles(Boolean(cfg.embed_subtitles));
      }
    }).catch(() => {});
  }, []);

  const handleSaveConfig = async () => {
    await api.updateConfig({
      download_dir: downloadDir,
      concurrent_downloads: concurrency,
      sponsorblock_enabled: sponsorblockEnabled,
      embed_thumbnail: embedThumbnail,
      embed_metadata: embedMetadata,
      embed_subtitles: embedSubtitles,
    });
    setSavedToast(true);
    setTimeout(() => setSavedToast(false), 3000);
  };

  return (
    <div className="p-8 space-y-10 max-w-7xl mx-auto pb-28">
      {/* Header */}
      <div className="flex items-center justify-between pb-6 border-b border-border">
        <div>
          <h1 className="text-3xl font-black text-foreground tracking-tight">Settings & Customization</h1>
          <p className="text-sm text-foreground-muted mt-1">
            Configure preset themes, audio DSP, SponsorBlock, and downloader paths.
          </p>
        </div>

        {savedToast && (
          <div className="flex items-center gap-2 px-4 py-2 rounded-2xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 text-xs font-bold animate-fadeIn">
            <Check className="w-4 h-4" />
            <span>Settings Saved!</span>
          </div>
        )}
      </div>

      {/* 30+ Themes Grid Section */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <Palette className="w-6 h-6 text-primary" />
          <h2 className="text-xl font-bold text-foreground">Theme Presets (from ytm-rs & BitChord)</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {THEME_PRESETS.map((theme) => {
            const isSelected = currentThemeId === theme.id;
            return (
              <div
                key={theme.id}
                onClick={() => setTheme(theme.id)}
                className={`p-4 rounded-2xl border cursor-pointer transition-all duration-200 relative group flex flex-col justify-between ${
                  isSelected
                    ? 'border-primary ring-2 ring-primary/30 shadow-lg shadow-primary/20 bg-surface-elevated'
                    : 'border-border bg-surface hover:border-primary/40 hover:-translate-y-0.5'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-sm text-foreground">{theme.name}</span>
                    {isSelected && (
                      <span className="w-5 h-5 rounded-full bg-primary text-white flex items-center justify-center">
                        <Check className="w-3.5 h-3.5 stroke-[3]" />
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-foreground-muted line-clamp-2">{theme.description}</p>
                </div>

                {/* Color Swatches */}
                <div className="flex items-center gap-1.5 mt-4 pt-3 border-t border-border/40">
                  <div
                    className="w-5 h-5 rounded-full border border-white/20 shadow-sm"
                    style={{ backgroundColor: theme.colors.bgMain }}
                    title="Background"
                  />
                  <div
                    className="w-5 h-5 rounded-full border border-white/20 shadow-sm"
                    style={{ backgroundColor: theme.colors.bgSurface }}
                    title="Surface"
                  />
                  <div
                    className="w-5 h-5 rounded-full border border-white/20 shadow-sm"
                    style={{ backgroundColor: theme.colors.primary }}
                    title="Primary"
                  />
                  <div
                    className="w-5 h-5 rounded-full border border-white/20 shadow-sm"
                    style={{ backgroundColor: theme.colors.accent }}
                    title="Accent"
                  />
                  <span className="text-[10px] text-foreground-subtle ml-auto font-mono">
                    {theme.category}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Audio Engine Configuration */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <Volume2 className="w-6 h-6 text-primary" />
          <h2 className="text-xl font-bold text-foreground">Audio Playback & SponsorBlock</h2>
        </div>

        <div className="bg-surface border border-border rounded-3xl p-6 shadow-xl space-y-6">
          {/* Crossfade Slider */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h4 className="font-bold text-sm text-foreground">Gapless Playback & Crossfade</h4>
              <p className="text-xs text-foreground-muted">
                Smoothly blend track transitions from 0 to 12 seconds.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="0"
                max="12"
                step="1"
                value={crossfadeSeconds}
                onChange={(e) => setCrossfade(parseInt(e.target.value))}
                className="w-36 h-2 bg-surface-elevated rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <span className="font-mono text-xs font-bold text-primary w-8">
                {crossfadeSeconds}s
              </span>
            </div>
          </div>

          {/* SponsorBlock Auto-Skip */}
          <div className="flex items-center justify-between pt-4 border-t border-border/50">
            <div>
              <h4 className="font-bold text-sm text-foreground flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-primary" />
                <span>SponsorBlock Auto-Skipping</span>
              </h4>
              <p className="text-xs text-foreground-muted">
                Automatically skips non-music intros, music video dialog, sponsors, and outro banter.
              </p>
            </div>
            <input
              type="checkbox"
              checked={sponsorblockEnabled}
              onChange={(e) => {
                setSponsorblockEnabled(e.target.checked);
                api.updateConfig({ sponsorblock_enabled: e.target.checked });
              }}
              className="w-5 h-5 rounded accent-primary cursor-pointer"
            />
          </div>
        </div>
      </section>

      {/* Downloader Settings */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <Download className="w-6 h-6 text-primary" />
          <h2 className="text-xl font-bold text-foreground">Downloader Engine Settings</h2>
        </div>

        <div className="bg-surface border border-border rounded-3xl p-6 shadow-xl space-y-6">
          {/* Download Directory Path */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-foreground-muted uppercase tracking-wider block">
              Download Destination Directory
            </label>
            <div className="flex gap-3">
              <input
                type="text"
                value={downloadDir}
                onChange={(e) => setDownloadDir(e.target.value)}
                className="flex-1 bg-surface-elevated border border-border focus:border-primary text-foreground text-sm rounded-2xl px-4 py-3 outline-none"
              />
              <button
                onClick={handleSaveConfig}
                className="px-5 py-3 rounded-2xl bg-primary text-white font-bold text-xs shadow-md shadow-primary/20 hover:scale-105 active:scale-95 transition-all"
              >
                Save Path
              </button>
            </div>
          </div>

          {/* Concurrent Downloads Slider */}
          <div className="flex items-center justify-between pt-4 border-t border-border/50">
            <div>
              <h4 className="font-bold text-sm text-foreground">Concurrent Workers</h4>
              <p className="text-xs text-foreground-muted">
                Number of simultaneous downloads in thread pool (1 to 8 workers).
              </p>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="1"
                max="8"
                step="1"
                value={concurrency}
                onChange={(e) => setConcurrency(parseInt(e.target.value))}
                className="w-32 h-2 bg-surface-elevated rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <span className="font-mono text-xs font-bold text-primary w-6 text-center">
                {concurrency}
              </span>
            </div>
          </div>

          {/* Embed Switches */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-border/50">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={embedThumbnail}
                onChange={(e) => setEmbedThumbnail(e.target.checked)}
                className="w-4 h-4 rounded accent-primary"
              />
              <span className="text-xs font-semibold text-foreground">Embed High-Res Cover Art</span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={embedMetadata}
                onChange={(e) => setEmbedMetadata(e.target.checked)}
                className="w-4 h-4 rounded accent-primary"
              />
              <span className="text-xs font-semibold text-foreground">Embed ID3 Audio Metadata</span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={embedSubtitles}
                onChange={(e) => setEmbedSubtitles(e.target.checked)}
                className="w-4 h-4 rounded accent-primary"
              />
              <span className="text-xs font-semibold text-foreground">Embed Video Subtitles</span>
            </label>
          </div>

          <div className="pt-2 text-right">
            <button
              onClick={handleSaveConfig}
              className="px-6 py-2.5 rounded-2xl bg-primary hover:bg-primary-hover text-white text-xs font-bold shadow-lg shadow-primary/20 transition-all"
            >
              Apply All Settings
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};
