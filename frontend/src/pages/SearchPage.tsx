import React, { useState } from 'react';
import { Search, Play, Download, Music, Video, User, Disc, ListMusic } from 'lucide-react';
import { api } from '../services/api';
import { Track } from '../types';
import { usePlayerStore } from '../stores/usePlayerStore';
import { useDownloadStore } from '../stores/useDownloadStore';

interface SearchPageProps {
  initialQuery?: string;
}

export const SearchPage: React.FC<SearchPageProps> = ({ initialQuery = '' }) => {
  const [query, setQuery] = useState(initialQuery);
  const [filter, setFilter] = useState<string>('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const { playTrack, setExpanded, setVideoMode } = usePlayerStore();
  const { queueDownload } = useDownloadStore();

  const handleSearch = async (searchFilter?: string) => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    const activeFilter = searchFilter !== undefined ? searchFilter : filter;
    try {
      const data = await api.search(query, activeFilter || undefined);
      setResults(data || []);
    } catch (err) {
      console.error('Search failed', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterClick = (newFilter: string) => {
    setFilter(newFilter);
    handleSearch(newFilter);
  };

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

  const filterTabs = [
    { id: '', label: 'All Results' },
    { id: 'songs', label: 'Songs', icon: Music },
    { id: 'videos', label: 'Videos', icon: Video },
    { id: 'albums', label: 'Albums', icon: Disc },
    { id: 'artists', label: 'Artists', icon: User },
    { id: 'playlists', label: 'Playlists', icon: ListMusic },
  ];

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto pb-28">
      {/* Search Header Form */}
      <div className="space-y-4">
        <h1 className="text-3xl font-black text-foreground tracking-tight">Search & Discover</h1>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-foreground-muted pointer-events-none" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search artists, tracks, podcasts, albums..."
              className="w-full bg-surface border border-border focus:border-primary text-foreground placeholder:text-foreground-subtle text-base rounded-2xl pl-12 pr-4 py-3.5 outline-none transition-all shadow-inner focus:ring-2 focus:ring-primary/20"
            />
          </div>
          <button
            onClick={() => handleSearch()}
            aria-label="Submit search"
            disabled={loading || !query.trim()}
            className="px-6 py-3.5 rounded-2xl bg-primary hover:bg-primary-hover text-white font-bold text-sm shadow-lg shadow-primary/25 disabled:opacity-50 transition-all hover:scale-105 active:scale-95"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>

        {/* Filter Tabs */}
        <div className="flex flex-wrap gap-2 pt-2">
          {filterTabs.map((tab) => {
            const isSelected = filter === tab.id;
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => handleFilterClick(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                  isSelected
                    ? 'bg-primary text-white shadow-md shadow-primary/20'
                    : 'bg-surface border border-border text-foreground-muted hover:text-foreground hover:bg-surface-elevated'
                }`}
              >
                {Icon && <Icon className="w-3.5 h-3.5" />}
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Results Section */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-foreground-muted">
          <div className="w-10 h-10 border-3 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-semibold">Searching YouTube Music...</span>
        </div>
      ) : searched && results.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-2 text-foreground-muted">
          <Search className="w-12 h-12 opacity-30 text-primary" />
          <p className="text-base font-semibold">No results found for "{query}"</p>
          <p className="text-xs text-foreground-subtle">Check your spelling or try broader keywords.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {results.map((item, idx) => {
            const isSong = Boolean(item.videoId || item.duration);
            return (
              <div
                key={item.id || idx}
                onClick={() => {
                  if (isSong) {
                    playTrack(item, results.filter((x) => x.videoId || x.duration));
                  }
                }}
                className="flex items-center justify-between p-3.5 rounded-2xl bg-surface border border-border hover:border-primary/40 hover:bg-surface-elevated cursor-pointer group transition-all"
              >
                <div className="flex items-center gap-4 min-w-0">
                  <div className="relative w-12 h-12 rounded-xl overflow-hidden bg-surface-elevated shrink-0 shadow-md">
                    <img
                      src={item.thumbnail || '/placeholder.png'}
                      alt=""
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                    />
                    {isSong && (
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                        <Play className="w-5 h-5 text-white fill-current ml-0.5" />
                      </div>
                    )}
                  </div>
                  <div className="min-w-0">
                    <h4 className="font-semibold text-sm text-foreground truncate group-hover:text-primary transition-colors">
                      {item.title}
                    </h4>
                    <p className="text-xs text-foreground-muted truncate">
                      {item.artist || item.uploader || item.resultType || 'Track'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {isSong && (
                    <>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          playTrack(item, results.filter((x) => x.videoId || x.duration));
                          setVideoMode(true);
                          setExpanded(true);
                        }}
                        title="Watch YouTube Video"
                        className="p-2 rounded-xl hover:bg-surface text-foreground-muted hover:text-primary opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Video className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => handleDownload(e, item)}
                        title="Download 320k MP3"
                        className="p-2 rounded-xl hover:bg-surface text-foreground-muted hover:text-foreground opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                    </>
                  )}
                  {item.duration && (
                    <span className="text-xs font-mono text-foreground-subtle min-w-[45px] text-right">
                      {item.duration}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
