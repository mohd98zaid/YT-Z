import React, { useState, useEffect, useRef } from 'react';
import { Search, Sliders, Palette, X, Sparkles } from 'lucide-react';
import { api } from '../services/api';
import { useThemeStore } from '../stores/useThemeStore';
import { usePlayerStore } from '../stores/usePlayerStore';

interface HeaderProps {
  onSearchSubmit: (query: string) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
}

export const Header: React.FC<HeaderProps> = ({
  onSearchSubmit,
  searchQuery,
  setSearchQuery,
}) => {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const { currentTheme, setTheme } = useThemeStore();
  const { toggleEqualizer, eqEnabled } = usePlayerStore();
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.length < 2) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(() => {
      api.getSuggestions(searchQuery).then((res) => {
        setSuggestions(res || []);
      }).catch(() => {});
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Click outside to close suggestions
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && searchQuery.trim()) {
      setShowDropdown(false);
      onSearchSubmit(searchQuery);
    }
  };

  return (
    <header className="h-16 border-b border-border bg-surface/80 backdrop-blur-md px-6 flex items-center justify-between z-10 shrink-0">
      {/* Search Input Bar with Autocomplete */}
      <div className="relative w-full max-w-xl" ref={dropdownRef}>
        <div className="relative flex items-center">
          <Search className="w-4 h-4 absolute left-3.5 text-foreground-muted pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setShowDropdown(true);
            }}
            onFocus={() => setShowDropdown(true)}
            onKeyDown={handleKeyDown}
            placeholder="Search songs, artists, albums, or paste YouTube/Spotify link..."
            className="w-full bg-surface-elevated/70 border border-border focus:border-primary/50 text-foreground placeholder:text-foreground-subtle text-sm rounded-full pl-10 pr-9 py-2 outline-none transition-all duration-200 focus:bg-surface-elevated focus:ring-2 focus:ring-primary/20"
          />
          {searchQuery && (
            <button
              onClick={() => {
                setSearchQuery('');
                setSuggestions([]);
              }}
              className="absolute right-3 p-0.5 rounded-full hover:bg-surface text-foreground-muted hover:text-foreground"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Autocomplete Dropdown */}
        {showDropdown && suggestions.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-surface-elevated border border-border rounded-2xl shadow-2xl py-2 z-50 backdrop-blur-xl max-h-72 overflow-y-auto">
            {suggestions.map((item, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setSearchQuery(item);
                  setShowDropdown(false);
                  onSearchSubmit(item);
                }}
                className="w-full text-left px-4 py-2 hover:bg-primary/10 hover:text-primary text-sm text-foreground flex items-center gap-2.5 transition-colors"
              >
                <Search className="w-3.5 h-3.5 text-foreground-muted" />
                <span>{item}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Header Quick Actions */}
      <div className="flex items-center gap-2 ml-4">
        {/* Equalizer Quick Toggle */}
        <button
          onClick={toggleEqualizer}
          title="10-Band Graphic Equalizer"
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
            eqEnabled
              ? 'bg-primary/10 text-primary border-primary/30 hover:bg-primary/20'
              : 'bg-surface-elevated text-foreground-muted border-border hover:text-foreground'
          }`}
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>EQ</span>
        </button>

        {/* Theme Indicator */}
        <div
          title={`Active Theme: ${currentTheme.name}`}
          className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-elevated border border-border text-xs text-foreground-muted font-medium"
        >
          <Palette className="w-3.5 h-3.5 text-primary" />
          <span className="hidden sm:inline">{currentTheme.name}</span>
          <div
            className="w-3 h-3 rounded-full border border-white/20 shadow-sm"
            style={{ backgroundColor: currentTheme.colors.primary }}
          />
        </div>
      </div>
    </header>
  );
};
