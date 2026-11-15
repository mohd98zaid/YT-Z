import React, { useState } from 'react';
import {
  ChevronDown,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Shuffle,
  Repeat,
  Repeat1,
  Volume2,
  VolumeX,
  Mic2,
  ListMusic,
  Sliders,
  Download,
  Info,
  Clock,
  Gauge,
  Video,
  Disc,
  Moon,
  Radio,
  ExternalLink,
  RefreshCw,
  Tv,
  Sparkles,
} from 'lucide-react';
import { usePlayerStore } from '../../stores/usePlayerStore';
import { useDownloadStore } from '../../stores/useDownloadStore';
import { useNavigationStore } from '../../stores/useNavigationStore';
import { api } from '../../services/api';
import { LyricsView } from '../Lyrics/LyricsView';

export const ExpandedPlayer: React.FC = () => {
  const {
    currentTrack,
    queue,
    queueIndex,
    isPlaying,
    isLoading,
    currentTime,
    duration,
    volume,
    isMuted,
    playbackSpeed,
    shuffle,
    repeatMode,
    isExpanded,
    showStatsForNerds,
    audioStats,
    audioQuality,
    setAudioQuality,
    setExpanded,
    togglePlay,
    next,
    previous,
    seek,
    setVolume,
    toggleMute,
    setPlaybackSpeed,
    toggleShuffle,
    cycleRepeat,
    toggleEqualizer,
    toggleStatsForNerds,
    playTrack,
    pause,
    setActiveVideoSource,
    removeFromQueue,
    isVideoMode,
    setVideoMode,
    sleepTimerRemaining,
    sleepTimerStopAfterTrack,
    toggleSleepTimer,
    startRadio,
    skipSilence,
    toggleSkipSilence,
    volumeNormalization,
    toggleVolumeNormalization,
  } = usePlayerStore();

  const { queueDownload } = useDownloadStore();
  const { navigateToYouTube } = useNavigationStore();
  const [activeTab, setActiveTab] = useState<'lyrics' | 'queue'>('lyrics');
  const [downloadQueued, setDownloadQueued] = useState(false);
  const [matchedVideos, setMatchedVideos] = useState<string[]>([]);
  const [matchedIndex, setMatchedIndex] = useState(0);
  const [resolvingVideo, setResolvingVideo] = useState(false);

  // Automatically resolve official embeddable public video when entering Watch Video mode
  React.useEffect(() => {
    if (isVideoMode && currentTrack && !currentTrack.isLocal) {
      const rawId = currentTrack.videoId || currentTrack.id;
      setResolvingVideo(true);
      api.searchYouTubeVideos(`${currentTrack.title} ${currentTrack.artist} official video`, 4)
        .then((vids) => {
          if (vids && vids.length > 0) {
            // Priority: #1 top public search match, then raw ID, then alternate matches
            const topMatch = vids[0].videoId || vids[0].id;
            const rest = vids.slice(1).map((v) => v.videoId || v.id).filter(Boolean);
            const combined = Array.from(new Set([topMatch, rawId, ...rest]));
            setMatchedVideos(combined);
            setMatchedIndex(0);
          } else {
            setMatchedVideos([rawId]);
            setMatchedIndex(0);
          }
        })
        .catch(() => {
          setMatchedVideos([rawId]);
          setMatchedIndex(0);
        })
        .finally(() => setResolvingVideo(false));
    }
  }, [isVideoMode, currentTrack?.id]);

  // Listen for YouTube embed play events to ensure music is paused
  React.useEffect(() => {
    if (!isVideoMode) return;
    const handleMessage = (event: MessageEvent) => {
      try {
        const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
        if (data && data.event === 'infoDelivery' && data.info) {
          if (data.info.playerState === 1) {
            pause();
            setActiveVideoSource('expanded_video');
          }
        }
      } catch {}
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [isVideoMode, pause, setActiveVideoSource]);

  const currentVideoId =
    matchedVideos[matchedIndex] || (currentTrack ? currentTrack.videoId || currentTrack.id : '');

  const handleRedirectToInternalYouTube = () => {
    if (!currentTrack) return;
    setVideoMode(false);
    setActiveVideoSource(null);
    setExpanded(false);
    navigateToYouTube({
      id: currentVideoId,
      title: currentTrack.title,
      artist: currentTrack.artist,
    });
  };

  const handleCycleAlternateVideo = () => {
    if (matchedVideos.length > 1) {
      setMatchedIndex((prev) => (prev + 1) % matchedVideos.length);
    }
  };

  if (!isExpanded || !currentTrack) return null;

  const formatTime = (secs: number) => {
    if (isNaN(secs) || secs < 0) return '0:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  const handleDownloadCurrent = async () => {
    if (!currentTrack) return;
    try {
      const url = currentTrack.isLocal
        ? currentTrack.filePath || ''
        : `https://www.youtube.com/watch?v=${currentTrack.videoId || currentTrack.id}`;
      await queueDownload({
        url,
        download_type: 'audio',
        format: 'mp3',
        quality: '320',
        title: currentTrack.title,
        artist: currentTrack.artist,
        thumbnail: currentTrack.thumbnail,
      });
      setDownloadQueued(true);
      setTimeout(() => setDownloadQueued(false), 3000);
    } catch (err) {
      console.error('Failed to queue download', err);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background select-none overflow-hidden animate-fadeIn">
      {/* Blurred Ambient Backdrop Canvas */}
      <div
        className="absolute inset-0 bg-cover bg-center filter blur-3xl opacity-40 scale-125 pointer-events-none transition-all duration-1000"
        style={{
          backgroundImage: `url(${currentTrack.thumbnail})`,
        }}
      />
      <div className="absolute inset-0 bg-background/85 backdrop-blur-3xl pointer-events-none" />

      {/* Top Header Bar */}
      <header className="relative z-10 flex items-center justify-between px-8 py-5 border-b border-border/40">
        <button
          onClick={() => {
            setExpanded(false);
            if (isVideoMode) {
              setVideoMode(false);
              setActiveVideoSource(null);
            }
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface-elevated/70 border border-border text-foreground-muted hover:text-foreground text-xs font-semibold backdrop-blur-md transition-all hover:scale-105"
        >
          <ChevronDown className="w-4 h-4" />
          <span>Minimize</span>
        </button>

        {/* Tab Selector: Lyrics vs Up Next */}
        <div className="flex items-center gap-1 p-1 rounded-full bg-surface-elevated/80 border border-border backdrop-blur-md">
          <button
            onClick={() => setActiveTab('lyrics')}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold transition-all ${
              activeTab === 'lyrics'
                ? 'bg-primary text-white shadow-md shadow-primary/20'
                : 'text-foreground-muted hover:text-foreground'
            }`}
          >
            <Mic2 className="w-3.5 h-3.5" />
            <span>Synced Lyrics</span>
          </button>
          <button
            onClick={() => setActiveTab('queue')}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold transition-all ${
              activeTab === 'queue'
                ? 'bg-primary text-white shadow-md shadow-primary/20'
                : 'text-foreground-muted hover:text-foreground'
            }`}
          >
            <ListMusic className="w-3.5 h-3.5" />
            <span>Up Next ({queue.length})</span>
          </button>
        </div>

        {/* Right Action Icons */}
        <div className="flex items-center gap-2">
          {/* Endless Song Radio */}
          {!currentTrack.isLocal && (
            <button
              onClick={() => startRadio()}
              title="Start Endless Song Radio"
              className="p-2 rounded-full bg-surface-elevated/70 border border-border text-foreground-muted hover:text-primary transition-all hover:scale-105"
            >
              <Radio className="w-4 h-4" />
            </button>
          )}

          {/* Sleep Timer */}
          <button
            onClick={toggleSleepTimer}
            title="Sleep Timer"
            className={`p-2 rounded-full border transition-all hover:scale-105 relative ${
              sleepTimerRemaining !== null || sleepTimerStopAfterTrack
                ? 'bg-primary/20 text-primary border-primary/40'
                : 'bg-surface-elevated/70 text-foreground-muted border-border hover:text-foreground'
            }`}
          >
            <Moon className="w-4 h-4" />
            {(sleepTimerRemaining !== null || sleepTimerStopAfterTrack) && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-primary animate-ping" />
            )}
          </button>

          {/* Stats for nerds toggle */}
          <button
            onClick={toggleStatsForNerds}
            title="Stats for Nerds"
            className={`p-2 rounded-full border transition-all ${
              showStatsForNerds
                ? 'bg-primary/20 text-primary border-primary/40'
                : 'bg-surface-elevated/70 text-foreground-muted border-border hover:text-foreground'
            }`}
          >
            <Info className="w-4 h-4" />
          </button>

          {/* Equalizer toggle */}
          <button
            onClick={toggleEqualizer}
            title="Studio Equalizer"
            className="p-2 rounded-full bg-surface-elevated/70 border border-border text-foreground-muted hover:text-foreground transition-all hover:scale-105"
          >
            <Sliders className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Main Center Area: Split Artwork & Lyrics/Queue */}
      <div className="relative z-10 flex-1 flex flex-col md:flex-row items-center justify-between p-4 sm:p-6 md:p-8 gap-6 overflow-y-auto">
        {/* Left: Album Artwork with Vinyl Animation OR Embedded YouTube Video */}
        <div className="w-full md:w-1/2 flex flex-col items-center justify-center max-w-xl my-auto">
          {/* Song vs Video Mode Toggle Pill */}
          {!currentTrack.isLocal && (
            <div className="flex items-center gap-1 p-1 rounded-full bg-surface-elevated/80 border border-border mb-3 backdrop-blur-md shadow-lg shrink-0">
              <button
                onClick={() => {
                  setVideoMode(false);
                  setActiveVideoSource(null);
                }}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold transition-all ${
                  !isVideoMode
                    ? 'bg-primary text-white shadow-md shadow-primary/20'
                    : 'text-foreground-muted hover:text-foreground'
                }`}
              >
                <Disc className="w-3.5 h-3.5" />
                <span>Song & Vinyl</span>
              </button>
              <button
                onClick={() => {
                  setVideoMode(true);
                  pause();
                  setActiveVideoSource('expanded_video');
                }}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold transition-all ${
                  isVideoMode
                    ? 'bg-primary text-white shadow-md shadow-primary/20'
                    : 'text-foreground-muted hover:text-foreground'
                }`}
              >
                <Video className="w-3.5 h-3.5" />
                <span>Watch Video</span>
              </button>
            </div>
          )}

          {isVideoMode && !currentTrack.isLocal ? (
            <div className="w-full flex flex-col items-center gap-2.5">
              <div className="relative w-full aspect-video rounded-3xl overflow-hidden shadow-2xl border border-white/10 bg-black animate-fadeIn max-h-[45vh]">
                <iframe
                  key={currentVideoId}
                  src={`https://www.youtube-nocookie.com/embed/${currentVideoId}?autoplay=1&enablejsapi=1&controls=1&modestbranding=1&rel=0&iv_load_policy=3`}
                  title={currentTrack.title}
                  className="w-full h-full border-0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              </div>

              {/* Fallback & Internal YouTube Redirect Actions Toolbar */}
              <div className="flex flex-wrap items-center justify-center gap-2 pt-1 animate-fadeIn">
                {/* Redirect to Internal YouTube Theater */}
                <button
                  onClick={handleRedirectToInternalYouTube}
                  title="Watch inside internal YouTube Video Theater"
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-red-600 hover:bg-red-500 text-white text-[11px] font-bold shadow-md shadow-red-600/25 transition-all hover:scale-105 active:scale-95"
                >
                  <Tv className="w-3.5 h-3.5" />
                  <span>Open in YouTube Theater</span>
                </button>

                {/* Try Alternate YouTube Video from Search */}
                {matchedVideos.length > 1 && (
                  <button
                    onClick={handleCycleAlternateVideo}
                    title="Switch to alternative YouTube video source"
                    className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-surface-elevated hover:bg-border/60 text-foreground text-[11px] font-bold border border-border transition-all hover:scale-105 active:scale-95"
                  >
                    <RefreshCw className={`w-3 h-3 text-primary ${resolvingVideo ? 'animate-spin' : ''}`} />
                    <span>Try Alternate Video ({matchedIndex + 1}/{matchedVideos.length})</span>
                  </button>
                )}

                {/* Return to Song Artwork */}
                <button
                  onClick={() => {
                    setVideoMode(false);
                    setActiveVideoSource(null);
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface-elevated/70 hover:bg-surface-elevated text-foreground-muted hover:text-foreground text-[11px] font-bold transition-all"
                >
                  <Disc className="w-3 h-3" />
                  <span>Song Deck</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="relative group w-48 h-48 sm:w-64 sm:h-64 md:w-72 md:h-72 lg:w-80 lg:h-80 max-h-[38vh] max-w-[38vh]">
              {/* Spinning Vinyl Record Layer Behind Artwork */}
              <div
                className={`absolute -right-8 top-1/2 -translate-y-1/2 w-44 h-44 sm:w-56 sm:h-56 md:w-64 md:h-64 lg:w-72 lg:h-72 rounded-full bg-zinc-950 border-4 border-zinc-800 shadow-2xl flex items-center justify-center ${
                  isPlaying ? 'animate-spin-slow' : ''
                }`}
              >
                <div className="w-20 h-20 rounded-full border-4 border-zinc-700/80 bg-zinc-900 flex items-center justify-center">
                  <div className="w-5 h-5 rounded-full bg-primary/80" />
                </div>
              </div>

              {/* High-res Full-bleed Cover Artwork */}
              <div className="relative w-full h-full rounded-3xl overflow-hidden shadow-2xl border border-white/10 z-10 bg-surface">
                <img
                  src={currentTrack.thumbnail || '/placeholder.png'}
                  alt={currentTrack.title}
                  className="w-full h-full object-cover"
                />
              </div>
            </div>
          )}

          {/* Track Details */}
          <div className="mt-4 text-center w-full px-4">
            <h2 className="text-2xl md:text-3xl font-black text-foreground tracking-tight truncate">
              {currentTrack.title}
            </h2>
            <p className="text-base text-foreground-muted font-medium mt-1 truncate">
              {currentTrack.artist}
            </p>
            {currentTrack.album && (
              <p className="text-xs text-foreground-subtle mt-0.5">{currentTrack.album}</p>
            )}

            {/* Apple Music / BitChord Hi-Res Lossless Audio Badge */}
            <div className="mt-3 flex items-center justify-center gap-2">
              {audioStats?.isLossless ? (
                <button
                  onClick={toggleStatsForNerds}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-black tracking-wider bg-gradient-to-r from-amber-500/20 via-yellow-500/25 to-amber-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_12px_rgba(245,158,11,0.3)] hover:scale-105 transition-all"
                  title="Bit-Perfect Lossless FLAC via BitChord Addon Engine"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>{audioStats?.qualityTier === 'hi-res' ? 'HI-RES LOSSLESS' : 'LOSSLESS'}</span>
                  <span className="text-[10px] opacity-80 font-mono font-normal">
                    {audioStats.format || 'FLAC'} · {audioStats.bitDepth || 16}-bit/{Math.round((audioStats.sampleRate || 44100) / 1000)}kHz
                  </span>
                </button>
              ) : (
                <button
                  onClick={toggleStatsForNerds}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-surface-elevated/80 text-foreground-muted border border-border/60 hover:text-foreground hover:scale-105 transition-all"
                  title="Standard YouTube Music Opus stream (Click for Stats & Lossless Switch)"
                >
                  <span className="uppercase font-bold">{audioStats?.codec || 'OPUS'}</span>
                  <span className="text-[10px] opacity-75">· {audioStats?.bitrate || 256} kbps</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Right: Synced Lyrics View or Up Next Queue */}
        <div className="w-full md:w-1/2 h-full flex flex-col bg-surface/40 border border-border/40 rounded-3xl backdrop-blur-xl overflow-hidden relative shadow-2xl">
          {showStatsForNerds && audioStats ? (
            <div className="h-full bg-surface border border-white/10 p-6 z-30 flex flex-col justify-between text-xs font-mono text-foreground overflow-y-auto rounded-3xl">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-primary flex items-center gap-2">
                    <Gauge className="w-4 h-4" />
                    <span>Stats for Nerds (Audio Engine & BitChord Add-ons)</span>
                  </h4>
                  {audioStats.isLossless && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-black tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/40">
                      BIT-PERFECT
                    </span>
                  )}
                </div>

                <div className="space-y-2.5">
                  <div className="flex justify-between py-1 border-b border-border/50">
                    <span className="text-foreground-muted">Track:</span>
                    <span className="truncate max-w-[240px] text-right font-medium">{currentTrack.title}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/50">
                    <span className="text-foreground-muted">Audio Codec:</span>
                    <span className="uppercase text-emerald-400 font-bold">{audioStats.codec}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/50">
                    <span className="text-foreground-muted">Bitrate:</span>
                    <span className="text-primary font-bold">{audioStats.bitrate} kbps</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/50">
                    <span className="text-foreground-muted">Resolution:</span>
                    <span className="text-amber-400 font-semibold">
                      {audioStats.bitDepth || 16}-bit / {audioStats.sampleRate || 44100} Hz
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/50">
                    <span className="text-foreground-muted">Active Source Provider:</span>
                    <span className="text-foreground font-semibold">{audioStats.provider}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/50">
                    <span className="text-foreground-muted">Output Channel:</span>
                    <span>Direct WebAudio 10-Band EQ Engine</span>
                  </div>
                </div>

                {/* Stream Quality Selector (BitChord Mode) */}
                <div className="pt-2">
                  <div className="text-[11px] font-bold text-foreground-muted uppercase tracking-wider mb-2">
                    Audio Quality Target
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { id: 'lossless', label: 'Lossless FLAC', desc: 'Bit-perfect 1411k+' },
                      { id: 'high', label: 'High (320k)', desc: 'Enhanced bitrate' },
                      { id: 'auto', label: 'Standard', desc: 'YouTube Opus 256k' },
                    ].map((mode) => (
                      <button
                        key={mode.id}
                        onClick={() => setAudioQuality(mode.id as any)}
                        className={`p-2 rounded-xl border text-left transition-all ${
                          audioQuality === mode.id
                            ? 'bg-primary/20 border-primary text-primary shadow-sm shadow-primary/20'
                            : 'bg-surface-elevated/60 border-border/60 text-foreground-muted hover:text-foreground hover:bg-surface-elevated'
                        }`}
                      >
                        <div className="font-bold text-[11px] leading-tight">{mode.label}</div>
                        <div className="text-[9px] opacity-70 mt-0.5">{mode.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <button
                onClick={toggleStatsForNerds}
                className="w-full mt-4 py-2.5 rounded-xl bg-surface-elevated hover:bg-surface-elevated/80 text-foreground font-semibold transition-colors"
              >
                Close Stats
              </button>
            </div>
          ) : activeTab === 'lyrics' ? (
            <LyricsView />
          ) : (
            <div className="h-full flex flex-col p-4 overflow-hidden">
              <div className="px-3 py-2 text-xs font-bold text-foreground-muted uppercase tracking-wider">
                Up Next Queue
              </div>
              <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                {queue.map((t, idx) => {
                  const isCurrent = idx === queueIndex;
                  return (
                    <div
                      key={`${t.id}_${idx}`}
                      onClick={() => playTrack(t)}
                      className={`flex items-center justify-between p-3 rounded-2xl cursor-pointer transition-all ${
                        isCurrent
                          ? 'bg-primary/20 border border-primary/30 text-primary'
                          : 'hover:bg-surface-elevated/60 text-foreground'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <img
                          src={t.thumbnail}
                          alt=""
                          className="w-10 h-10 rounded-xl object-cover shrink-0"
                        />
                        <div className="min-w-0">
                          <p className="text-sm font-semibold truncate">{t.title}</p>
                          <p className="text-xs text-foreground-muted truncate">{t.artist}</p>
                        </div>
                      </div>
                      <span className="text-xs font-mono text-foreground-subtle ml-2">
                        {t.duration}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Expanded Controls Bar */}
      <footer className="relative z-10 px-8 py-6 bg-surface/80 border-t border-border/40 backdrop-blur-2xl flex flex-col items-center gap-4">
        {/* Progress Bar with Timers */}
        <div className="w-full max-w-2xl flex items-center gap-4">
          <span className="text-xs font-mono text-foreground-subtle w-10 text-right">
            {formatTime(currentTime)}
          </span>
          <div
            className="flex-1 h-2 bg-surface-elevated rounded-full cursor-pointer relative group overflow-hidden"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const pos = (e.clientX - rect.left) / rect.width;
              seek(pos * duration);
            }}
          >
            <div
              className="h-full bg-gradient-to-r from-primary to-accent rounded-full transition-all"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <span className="text-xs font-mono text-foreground-subtle w-10">
            {formatTime(duration)}
          </span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center justify-between w-full max-w-2xl">
          {/* Playback speed selector */}
          <div className="flex items-center gap-1">
            {[0.75, 1.0, 1.25, 1.5].map((spd) => (
              <button
                key={spd}
                onClick={() => setPlaybackSpeed(spd)}
                className={`px-2 py-0.5 rounded-lg text-[11px] font-bold ${
                  playbackSpeed === spd
                    ? 'bg-primary text-white'
                    : 'text-foreground-muted hover:text-foreground'
                }`}
              >
                {spd}x
              </button>
            ))}
          </div>

          {/* Primary Buttons */}
          <div className="flex items-center gap-6">
            <button
              onClick={toggleShuffle}
              className={`p-2 rounded-full ${
                shuffle ? 'text-primary' : 'text-foreground-muted hover:text-foreground'
              }`}
            >
              <Shuffle className="w-5 h-5" />
            </button>

            <button onClick={previous} className="text-foreground hover:scale-110 transition-transform">
              <SkipBack className="w-7 h-7 fill-current" />
            </button>

            <button
              onClick={togglePlay}
              disabled={isLoading}
              className="w-14 h-14 rounded-full bg-primary hover:bg-primary-hover text-white flex items-center justify-center shadow-xl shadow-primary/30 hover:scale-105 active:scale-95 transition-all"
            >
              {isLoading ? (
                <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin" />
              ) : isPlaying ? (
                <Pause className="w-7 h-7 fill-current" />
              ) : (
                <Play className="w-7 h-7 fill-current ml-1" />
              )}
            </button>

            <button onClick={next} className="text-foreground hover:scale-110 transition-transform">
              <SkipForward className="w-7 h-7 fill-current" />
            </button>

            <button
              onClick={cycleRepeat}
              className={`p-2 rounded-full ${
                repeatMode !== 'off' ? 'text-primary' : 'text-foreground-muted hover:text-foreground'
              }`}
            >
              {repeatMode === 'one' ? <Repeat1 className="w-5 h-5" /> : <Repeat className="w-5 h-5" />}
            </button>
          </div>

          {/* 1-Click Download in Expanded Player */}
          <button
            onClick={handleDownloadCurrent}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold border transition-all ${
              downloadQueued
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                : 'bg-surface-elevated text-foreground-muted border-border hover:text-foreground hover:scale-105'
            }`}
          >
            <Download className="w-4 h-4" />
            <span>{downloadQueued ? 'Queued!' : 'Download 320k'}</span>
          </button>
        </div>
      </footer>
    </div>
  );
};
