import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Search,
  Download,
  ExternalLink,
  Flame,
  Film,
  Sparkles,
  Maximize2,
  ListPlus,
  Tv,
  Check,
  Clipboard,
  X,
} from 'lucide-react';
import { api } from '../services/api';
import { Track } from '../types';
import { usePlayerStore } from '../stores/usePlayerStore';
import { useDownloadStore } from '../stores/useDownloadStore';
import { useNavigationStore } from '../stores/useNavigationStore';

// Authentic YouTube Play Icon
const YouTubeIcon: React.FC<{ className?: string }> = ({ className = 'w-6 h-6' }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
  </svg>
);

function extractYouTubeId(url: string): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  if (/^[a-zA-Z0-9_-]{11}$/.test(trimmed)) {
    return trimmed;
  }
  const match = trimmed.match(
    /(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=|shorts\/))([\w-]{11})/
  );
  return match ? match[1] : null;
}

export const YouTubePage: React.FC = () => {
  const [urlInput, setUrlInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeVideoId, setActiveVideoId] = useState<string | null>(null);
  const [activeVideoTitle, setActiveVideoTitle] = useState<string>('YouTube Video');
  const [activeVideoAuthor, setActiveVideoAuthor] = useState<string>('');
  const [trendingVideos, setTrendingVideos] = useState<Track[]>([]);
  const [searchResults, setSearchResults] = useState<Track[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [copiedToast, setCopiedToast] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);

  const { isPlaying, pause, setActiveVideoSource, playTrack } = usePlayerStore();
  const { queueDownload } = useDownloadStore();
  const youtubeSelectedVideo = useNavigationStore((s) => s.youtubeSelectedVideo);

  // 1. When video becomes active in YouTube Theater, immediately pause music playback
  useEffect(() => {
    if (activeVideoId) {
      pause();
      setActiveVideoSource('youtube_theater');
    } else {
      if (usePlayerStore.getState().activeVideoSource === 'youtube_theater') {
        setActiveVideoSource(null);
      }
    }
  }, [activeVideoId, pause, setActiveVideoSource]);

  // Clean up active video source on unmount
  useEffect(() => {
    return () => {
      if (usePlayerStore.getState().activeVideoSource === 'youtube_theater') {
        usePlayerStore.getState().setActiveVideoSource(null);
      }
    };
  }, []);

  // 2. If music starts playing anywhere, pause the active YouTube video iframe
  useEffect(() => {
    if (isPlaying && activeVideoId && iframeRef.current?.contentWindow) {
      try {
        iframeRef.current.contentWindow.postMessage(
          JSON.stringify({ event: 'command', func: 'pauseVideo', args: '' }),
          '*'
        );
      } catch (err) {
        console.debug('Failed to pause iframe video', err);
      }
    }
  }, [isPlaying, activeVideoId]);

  // 3. Listen to YouTube embed events (when user clicks play inside embed iframe)
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      try {
        const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
        if (data && data.event === 'infoDelivery' && data.info) {
          // playerState 1 = PLAYING
          if (data.info.playerState === 1) {
            usePlayerStore.getState().pause();
            usePlayerStore.getState().setActiveVideoSource('youtube_theater');
          }
        }
      } catch {}
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  // Auto-play video redirected from other components
  useEffect(() => {
    if (youtubeSelectedVideo && youtubeSelectedVideo.id) {
      setActiveVideoId(youtubeSelectedVideo.id);
      setActiveVideoTitle(youtubeSelectedVideo.title);
      setActiveVideoAuthor(youtubeSelectedVideo.artist || 'YouTube');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [youtubeSelectedVideo]);

  // Load Trending YouTube Videos on mount (no automatic autoplay)
  useEffect(() => {
    setLoading(true);
    api.getCharts()
      .then((charts) => {
        if (charts && charts.videos && charts.videos.length > 0) {
          setTrendingVideos(charts.videos);
        }
      })
      .catch((err) => console.error('Failed to load trending videos', err))
      .finally(() => setLoading(false));
  }, []);

  const handlePlayUrl = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const id = extractYouTubeId(urlInput);
    if (id) {
      setActiveVideoId(id);
      setActiveVideoTitle(`YouTube Video (${id})`);
      setActiveVideoAuthor('YouTube');
      setUrlInput('');
    } else {
      alert('Please enter a valid YouTube video URL or 11-character video ID.');
    }
  };

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setUrlInput(text);
        const id = extractYouTubeId(text);
        if (id) {
          setActiveVideoId(id);
          setActiveVideoTitle(`YouTube Video (${id})`);
          setActiveVideoAuthor('YouTube');
          setCopiedToast(true);
          setTimeout(() => setCopiedToast(false), 2000);
        }
      }
    } catch {
      // Fallback if clipboard api blocked
    }
  };

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    try {
      const data = await api.searchYouTubeVideos(searchQuery);
      setSearchResults(data || []);
    } catch (err) {
      console.error('Failed to search YouTube videos', err);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleSelectVideo = (video: Track) => {
    const id = video.videoId || video.id;
    setActiveVideoId(id);
    setActiveVideoTitle(video.title);
    setActiveVideoAuthor(video.artist || 'YouTube');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleDownloadVideo = (id: string, title: string, author: string, isAudio = false) => {
    queueDownload({
      url: `https://www.youtube.com/watch?v=${id}`,
      download_type: isAudio ? 'audio' : 'video',
      format: isAudio ? 'mp3' : 'mp4',
      quality: isAudio ? '320' : '1080',
      title: title || 'YouTube Video',
      artist: author || 'YouTube',
    });
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto pb-28">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-border">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-red-600/20 text-red-500 border border-red-500/30 flex items-center justify-center shadow-lg shadow-red-500/10">
            <YouTubeIcon className="w-7 h-7" />
          </div>
          <div>
            <h1 className="text-3xl font-black text-foreground tracking-tight flex items-center gap-2">
              <span>YouTube Video Theater</span>
            </h1>
            <p className="text-xs text-foreground-muted mt-0.5">
              Play any YouTube video directly in HD, watch trending videos, or paste any video link.
            </p>
          </div>
        </div>

        {/* Quick URL Bar */}
        <form onSubmit={handlePlayUrl} className="flex items-center gap-2 max-w-md w-full">
          <div className="relative flex-1">
            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="Paste any YouTube URL or Video ID..."
              className="w-full bg-surface border border-border focus:border-red-500 text-foreground placeholder:text-foreground-subtle text-xs rounded-2xl pl-4 pr-10 py-3 outline-none transition-all shadow-inner"
            />
            <button
              type="button"
              onClick={handlePaste}
              title="Paste from Clipboard"
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1.5 rounded-xl hover:bg-surface-elevated text-foreground-muted hover:text-foreground transition-colors"
            >
              <Clipboard className="w-3.5 h-3.5" />
            </button>
          </div>
          <button
            type="submit"
            className="px-5 py-3 rounded-2xl bg-red-600 hover:bg-red-500 text-white font-bold text-xs shadow-lg shadow-red-600/25 transition-all hover:scale-105 active:scale-95 shrink-0 flex items-center gap-1.5"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Play Video</span>
          </button>
        </form>
      </div>

      {/* Main Theater Player Section (only when a video is selected) */}
      {activeVideoId ? (
        <div className="bg-surface border border-border rounded-3xl p-5 shadow-2xl space-y-4 animate-fadeIn relative">
          <div className="flex items-center justify-between pb-1">
            <span className="text-xs font-bold text-red-500 flex items-center gap-1.5 uppercase tracking-wider">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              Now Playing
            </span>
            <button
              onClick={() => {
                if (iframeRef.current?.contentWindow) {
                  try {
                    iframeRef.current.contentWindow.postMessage(
                      JSON.stringify({ event: 'command', func: 'pauseVideo', args: '' }),
                      '*'
                    );
                  } catch {}
                }
                setActiveVideoId(null);
                setActiveVideoSource(null);
              }}
              className="flex items-center gap-1 text-xs font-semibold text-foreground-muted hover:text-foreground hover:bg-surface-elevated px-2.5 py-1 rounded-xl transition-colors border border-border/50"
            >
              <X className="w-3.5 h-3.5" />
              <span>Close Video</span>
            </button>
          </div>

          {/* 16:9 Cinema Screen */}
          <div className="relative w-full aspect-video rounded-2xl overflow-hidden bg-black shadow-2xl border border-white/10 max-h-[65vh]">
            <iframe
              ref={iframeRef}
              src={`https://www.youtube-nocookie.com/embed/${activeVideoId}?autoplay=1&enablejsapi=1&controls=1&modestbranding=1&rel=0&iv_load_policy=3`}
              title={activeVideoTitle}
              className="w-full h-full border-0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
            />
          </div>

          {/* Under-Video Details & Quick Actions Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-1">
            <div className="min-w-0">
              <h2 className="text-xl font-bold text-foreground truncate">{activeVideoTitle}</h2>
              <p className="text-xs text-foreground-muted truncate mt-0.5">{activeVideoAuthor}</p>
            </div>

            <div className="flex flex-wrap items-center gap-2 shrink-0">
              {/* Play Audio in Global Player (seamless transition from video to audio) */}
              <button
                onClick={() => {
                  if (iframeRef.current?.contentWindow) {
                    try {
                      iframeRef.current.contentWindow.postMessage(
                        JSON.stringify({ event: 'command', func: 'pauseVideo', args: '' }),
                        '*'
                      );
                    } catch {}
                  }
                  const vId = activeVideoId;
                  const vTitle = activeVideoTitle;
                  const vAuthor = activeVideoAuthor;
                  setActiveVideoId(null);
                  setActiveVideoSource(null);
                  playTrack({
                    id: vId,
                    videoId: vId,
                    title: vTitle,
                    artist: vAuthor,
                    thumbnail: `https://i.ytimg.com/vi/${vId}/hqdefault.jpg`,
                    duration: '0:00',
                    durationSeconds: 0,
                  });
                }}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-surface-elevated hover:bg-border/60 text-xs font-bold text-foreground transition-all hover:scale-105 active:scale-95"
              >
                <ListPlus className="w-3.5 h-3.5 text-primary" />
                <span>Listen as Audio</span>
              </button>

              {/* Download 4K Video */}
              <button
                onClick={() =>
                  handleDownloadVideo(activeVideoId, activeVideoTitle, activeVideoAuthor, false)
                }
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-surface-elevated hover:bg-border/60 text-xs font-bold text-foreground transition-all hover:scale-105 active:scale-95"
              >
                <Download className="w-3.5 h-3.5 text-emerald-400" />
                <span>Download Video</span>
              </button>

              {/* Download 320k MP3 */}
              <button
                onClick={() =>
                  handleDownloadVideo(activeVideoId, activeVideoTitle, activeVideoAuthor, true)
                }
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-surface-elevated hover:bg-border/60 text-xs font-bold text-foreground transition-all hover:scale-105 active:scale-95"
              >
                <Download className="w-3.5 h-3.5 text-pink-400" />
                <span>Download MP3</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Welcome Placeholder when no video is playing */
        <div className="bg-gradient-to-r from-surface via-surface-elevated/40 to-surface border border-border rounded-3xl p-8 shadow-xl text-center flex flex-col items-center justify-center gap-3 animate-fadeIn">
          <div className="w-14 h-14 rounded-3xl bg-red-600/10 text-red-500 border border-red-500/20 flex items-center justify-center shadow-lg">
            <YouTubeIcon className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-foreground">Ready to Watch</h2>
          <p className="text-xs text-foreground-muted max-w-md">
            Paste any YouTube video link in the bar above, search for any video below, or click any video card to start playing.
          </p>
        </div>
      )}

      {/* Search Any YouTube Video Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Search className="w-5 h-5 text-red-500" />
            <h3 className="text-xl font-bold text-foreground">Search Any YouTube Video</h3>
          </div>
        </div>

        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-foreground-muted" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search tutorials, live streams, music videos, podcasts..."
              className="w-full bg-surface border border-border focus:border-red-500 text-foreground placeholder:text-foreground-subtle text-xs rounded-2xl pl-11 pr-4 py-3 outline-none transition-all shadow-inner"
            />
          </div>
          <button
            type="submit"
            disabled={searchLoading || !searchQuery.trim()}
            className="px-6 py-3 rounded-2xl bg-red-600 hover:bg-red-500 text-white font-bold text-xs shadow-lg shadow-red-600/25 disabled:opacity-50 transition-all hover:scale-105 active:scale-95"
          >
            {searchLoading ? 'Searching...' : 'Search Videos'}
          </button>
        </form>

        {/* Search Results Grid */}
        {searchResults.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 pt-2">
            {searchResults.map((video, idx) => (
              <div
                key={video.id || idx}
                onClick={() => handleSelectVideo(video)}
                className="bg-surface border border-border hover:border-red-500/50 rounded-2xl p-3 cursor-pointer group transition-all hover:-translate-y-1 shadow-md flex flex-col justify-between"
              >
                <div className="relative aspect-video rounded-xl overflow-hidden bg-surface-elevated mb-2.5">
                  <img
                    src={video.thumbnail || `https://i.ytimg.com/vi/${video.videoId || video.id}/hqdefault.jpg`}
                    alt=""
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                  />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                    <div className="w-10 h-10 rounded-full bg-red-600 text-white flex items-center justify-center shadow-lg">
                      <Play className="w-5 h-5 fill-current ml-0.5" />
                    </div>
                  </div>
                  {video.duration && (
                    <span className="absolute bottom-2 right-2 bg-black/80 text-white text-[10px] font-mono font-bold px-1.5 py-0.5 rounded">
                      {video.duration}
                    </span>
                  )}
                </div>

                <div>
                  <h4 className="font-bold text-xs text-foreground line-clamp-2 group-hover:text-red-500 transition-colors">
                    {video.title}
                  </h4>
                  <div className="flex items-center justify-between mt-1 text-[11px] text-foreground-muted">
                    <span className="truncate">{video.artist || (video as any).uploader || 'YouTube Video'}</span>
                    {(video as any).views && (
                      <span className="shrink-0 font-medium text-foreground-subtle ml-1">
                        {(video as any).views}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Trending YouTube Videos Section */}
      <div className="space-y-4 pt-2">
        <div className="flex items-center gap-2">
          <Flame className="w-5 h-5 text-red-500" />
          <h3 className="text-xl font-bold text-foreground">Trending YouTube Music Videos</h3>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-foreground-muted">
            <div className="w-8 h-8 border-3 border-red-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-xs font-semibold">Loading trending videos...</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {trendingVideos.map((video, idx) => (
              <div
                key={video.id || idx}
                onClick={() => handleSelectVideo(video)}
                className="bg-surface border border-border hover:border-red-500/50 rounded-2xl p-3 cursor-pointer group transition-all hover:-translate-y-1 shadow-md flex flex-col justify-between"
              >
                <div className="relative aspect-video rounded-xl overflow-hidden bg-surface-elevated mb-2.5">
                  <img
                    src={video.thumbnail}
                    alt=""
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                  />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                    <div className="w-10 h-10 rounded-full bg-red-600 text-white flex items-center justify-center shadow-lg">
                      <Play className="w-5 h-5 fill-current ml-0.5" />
                    </div>
                  </div>
                  {video.duration && (
                    <span className="absolute bottom-2 right-2 bg-black/80 text-white text-[10px] font-mono font-bold px-1.5 py-0.5 rounded">
                      {video.duration}
                    </span>
                  )}
                </div>

                <div>
                  <h4 className="font-bold text-xs text-foreground line-clamp-2 group-hover:text-red-500 transition-colors">
                    {video.title}
                  </h4>
                  <p className="text-[11px] text-foreground-muted truncate mt-1">{video.artist}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
