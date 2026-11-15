import React, { useEffect, useState } from 'react';
import { Play, Download, Sparkles, TrendingUp, Music, Disc3 } from 'lucide-react';
import { api } from '../services/api';
import { Track } from '../types';
import { usePlayerStore } from '../stores/usePlayerStore';
import { useDownloadStore } from '../stores/useDownloadStore';

export const HomePage: React.FC = () => {
  const [sections, setSections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const { playTrack } = usePlayerStore();
  const { queueDownload } = useDownloadStore();

  useEffect(() => {
    api.getHome().then((data) => {
      setSections(data || []);
      setLoading(false);
    }).catch((err) => {
      console.error('Failed to load home feed', err);
      setLoading(false);
    });
  }, []);

  const handleDownload = (e: React.MouseEvent, track: Track) => {
    e.stopPropagation();
    queueDownload({
      url: `https://www.youtube.com/watch?v=${track.videoId || track.id}`,
      download_type: 'audio',
      format: 'mp3',
      quality: '320',
      title: track.title,
      artist: track.artist,
      thumbnail: track.thumbnail,
    });
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-foreground-muted">
        <div className="w-10 h-10 border-3 border-primary border-t-transparent rounded-full animate-spin" />
        <span className="text-sm font-semibold">Tuning into YouTube Music Feed...</span>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-10 max-w-7xl mx-auto pb-28">
      {/* Hero Welcome Banner */}
      <div className="relative rounded-3xl overflow-hidden p-8 border border-border bg-gradient-to-r from-surface-elevated via-surface to-surface-elevated/70 shadow-2xl">
        <div className="relative z-10 max-w-xl space-y-3">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary/20 text-primary text-xs font-extrabold border border-primary/30">
            <Sparkles className="w-3.5 h-3.5" />
            <span>YT-Z STREAMING & DOWNLOADER</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-foreground tracking-tight">
            High-Fidelity Audio & Studio Downloader
          </h1>
          <p className="text-sm text-foreground-muted leading-relaxed">
            Uncapped direct streaming, Apple-style word-synced lyrics, 30+ visual themes,
            and industrial-grade 4K & 320k MP3 concurrent downloading.
          </p>
        </div>
        <div className="absolute -right-8 -bottom-8 w-64 h-64 bg-primary/20 rounded-full filter blur-3xl pointer-events-none" />
      </div>

      {/* Dynamic Sections from YouTube Music */}
      {sections.map((section, sIdx) => (
        <section key={sIdx} className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-foreground tracking-tight flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              <span>{section.title}</span>
            </h2>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {section.items.map((item: any, iIdx: number) => {
              const isSong = Boolean(item.videoId || item.duration);
              return (
                <div
                  key={iIdx}
                  onClick={async () => {
                    if (isSong) {
                      playTrack(item, section.items.filter((x: any) => x.videoId || x.duration));
                    } else if (item.id || item.browseId) {
                      const id = item.id || item.browseId;
                      try {
                        const isPl =
                          item.type === 'playlist' ||
                          id.startsWith('RDCL') ||
                          id.startsWith('PL') ||
                          id.startsWith('VL') ||
                          id.startsWith('RD');
                        let data = isPl ? await api.getPlaylist(id) : await api.getAlbum(id);
                        if (!data || !data.tracks || data.tracks.length === 0) {
                          data = isPl ? await api.getAlbum(id) : await api.getPlaylist(id);
                        }
                        if (data && data.tracks && data.tracks.length > 0) {
                          playTrack(data.tracks[0], data.tracks);
                        }
                      } catch (err) {
                        console.error('Failed to load playlist/album', err);
                      }
                    }
                  }}
                  className="group relative bg-surface border border-border hover:border-primary/40 rounded-2xl p-3.5 flex flex-col justify-between cursor-pointer transition-all duration-200 hover:-translate-y-1 hover:shadow-xl"
                >
                  {/* Artwork Container */}
                  <div className="relative aspect-square w-full rounded-xl overflow-hidden bg-surface-elevated mb-3 shadow-md">
                    <img
                      src={item.thumbnail || '/placeholder.png'}
                      alt={item.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                    {/* Hover Overlay Play & Download Buttons */}
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                      <div className="w-10 h-10 rounded-full bg-primary text-white flex items-center justify-center shadow-lg hover:scale-110 active:scale-95 transition-transform">
                        <Play className="w-5 h-5 fill-current ml-0.5" />
                      </div>
                      {isSong && (
                        <button
                          onClick={(e) => handleDownload(e, item)}
                          title="Download 320k MP3"
                          className="w-9 h-9 rounded-full bg-surface-elevated/90 hover:bg-surface-elevated text-white flex items-center justify-center shadow-lg hover:scale-110 active:scale-95 transition-transform border border-white/20"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Metadata */}
                  <div className="space-y-1">
                    <h3 className="font-semibold text-sm text-foreground truncate group-hover:text-primary transition-colors">
                      {item.title}
                    </h3>
                    <p className="text-xs text-foreground-muted truncate">
                      {item.artist || item.subtitle || 'YouTube Music'}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
};
