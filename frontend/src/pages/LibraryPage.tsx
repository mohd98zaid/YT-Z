import React, { useEffect, useState } from 'react';
import { FolderHeart, Play, Folder, Heart, RefreshCw, Music, HardDrive } from 'lucide-react';
import { api } from '../services/api';
import { Track } from '../types';
import { usePlayerStore } from '../stores/usePlayerStore';

export const LibraryPage: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'favorites' | 'local'>('favorites');
  const [favorites, setFavorites] = useState<Track[]>([]);
  const [localFiles, setLocalFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const { playTrack } = usePlayerStore();

  const loadData = async () => {
    setLoading(true);
    try {
      const [favs, locals] = await Promise.all([api.getFavorites(), api.scanLibrary()]);
      setFavorites(favs || []);
      setLocalFiles(locals || []);
    } catch (err) {
      console.error('Failed to load library', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOpenExplorer = async (path?: string) => {
    if (!path) return;
    try {
      await api.openExplorer(path);
    } catch (err) {
      console.error('Failed to open explorer', err);
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto pb-28">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-border">
        <div>
          <h1 className="text-3xl font-black text-foreground tracking-tight flex items-center gap-3">
            <FolderHeart className="w-8 h-8 text-primary" />
            <span>My Music Library</span>
          </h1>
          <p className="text-sm text-foreground-muted mt-1">
            Access your offline downloaded songs, scanned local music folders, and saved favorites.
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-surface border border-border text-xs font-semibold text-foreground hover:bg-surface-elevated transition-all"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Library</span>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-border/50 pb-3">
        <button
          onClick={() => setActiveSubTab('favorites')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            activeSubTab === 'favorites'
              ? 'bg-primary text-white shadow-md shadow-primary/20'
              : 'text-foreground-muted hover:text-foreground hover:bg-surface-elevated'
          }`}
        >
          <Heart className="w-3.5 h-3.5 fill-current" />
          <span>Favorites ({favorites.length})</span>
        </button>
        <button
          onClick={() => setActiveSubTab('local')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            activeSubTab === 'local'
              ? 'bg-primary text-white shadow-md shadow-primary/20'
              : 'text-foreground-muted hover:text-foreground hover:bg-surface-elevated'
          }`}
        >
          <HardDrive className="w-3.5 h-3.5" />
          <span>Local Downloads ({localFiles.length})</span>
        </button>
      </div>

      {/* Tab Content */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-foreground-muted">
          <div className="w-10 h-10 border-3 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-semibold">Scanning files...</span>
        </div>
      ) : activeSubTab === 'favorites' ? (
        favorites.length === 0 ? (
          <div className="bg-surface border border-border rounded-3xl p-12 text-center text-foreground-muted space-y-2">
            <Heart className="w-10 h-10 opacity-30 text-primary mx-auto mb-2" />
            <p className="text-base font-bold text-foreground">No favorites yet</p>
            <p className="text-xs text-foreground-subtle">
              Click the heart icon on any playing song to add it here.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {favorites.map((track) => (
              <div
                key={track.id}
                onClick={() => playTrack(track, favorites)}
                className="flex items-center justify-between p-3.5 rounded-2xl bg-surface border border-border hover:border-primary/40 hover:bg-surface-elevated cursor-pointer group transition-all"
              >
                <div className="flex items-center gap-3.5 min-w-0">
                  <img
                    src={track.thumbnail || '/placeholder.png'}
                    alt=""
                    className="w-12 h-12 rounded-xl object-cover shrink-0 shadow-sm"
                  />
                  <div className="min-w-0">
                    <h4 className="font-semibold text-sm text-foreground truncate group-hover:text-primary transition-colors">
                      {track.title}
                    </h4>
                    <p className="text-xs text-foreground-muted truncate">{track.artist}</p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-foreground-subtle">{track.duration}</span>
                  <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <Play className="w-4 h-4 fill-current ml-0.5" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )
      ) : localFiles.length === 0 ? (
        <div className="bg-surface border border-border rounded-3xl p-12 text-center text-foreground-muted space-y-2">
          <HardDrive className="w-10 h-10 opacity-30 text-primary mx-auto mb-2" />
          <p className="text-base font-bold text-foreground">No local files found</p>
          <p className="text-xs text-foreground-subtle">
            Downloaded songs from the Downloader tab will automatically appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {localFiles.map((file) => (
            <div
              key={file.id}
              className="flex items-center justify-between p-3.5 rounded-2xl bg-surface border border-border hover:bg-surface-elevated transition-all group"
            >
              <div className="flex items-center gap-3.5 min-w-0">
                <div className="w-12 h-12 rounded-xl bg-surface-elevated flex items-center justify-center shrink-0 border border-border">
                  <Music className="w-5 h-5 text-primary" />
                </div>
                <div className="min-w-0">
                  <h4 className="font-semibold text-sm text-foreground truncate">{file.title}</h4>
                  <p className="text-xs text-foreground-muted truncate">
                    {file.artist} • <span className="uppercase font-bold">{file.extension}</span> •{' '}
                    {(file.fileSize / (1024 * 1024)).toFixed(1)} MB
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() =>
                    playTrack({
                      id: file.id,
                      videoId: file.id,
                      title: file.title,
                      artist: file.artist,
                      duration: file.duration,
                      durationSeconds: file.durationSeconds,
                      thumbnail: '',
                      isLocal: true,
                      filePath: file.filePath,
                    })
                  }
                  title="Play File"
                  className="p-2 rounded-xl bg-primary/10 hover:bg-primary text-primary hover:text-white transition-all"
                >
                  <Play className="w-4 h-4 fill-current ml-0.5" />
                </button>
                <button
                  onClick={() => handleOpenExplorer(file.filePath)}
                  title="Open in Windows Explorer"
                  className="p-2 rounded-xl bg-surface-elevated hover:bg-surface-elevated/80 text-foreground-muted hover:text-foreground transition-colors"
                >
                  <Folder className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
