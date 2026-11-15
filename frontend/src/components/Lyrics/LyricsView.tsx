import React, { useEffect, useRef } from 'react';
import { Mic2, Sparkles } from 'lucide-react';
import { usePlayerStore } from '../../stores/usePlayerStore';

export const LyricsView: React.FC = () => {
  const { currentTrack, lyrics, isLyricsLoading, currentTime, seek } = usePlayerStore();
  const containerRef = useRef<HTMLDivElement>(null);
  const activeLineRef = useRef<HTMLDivElement>(null);

  const lines = lyrics?.lines || [];

  // Determine active lyric line index based on currentTime
  let activeIndex = -1;
  for (let i = 0; i < lines.length; i++) {
    if (currentTime >= lines[i].time) {
      activeIndex = i;
    } else {
      break;
    }
  }

  // Smooth auto-scroll active lyric line to center of container
  useEffect(() => {
    if (activeLineRef.current && containerRef.current) {
      activeLineRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [activeIndex]);

  if (isLyricsLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-foreground-muted gap-3 py-16">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <span className="text-sm font-medium">Fetching synchronized lyrics...</span>
      </div>
    );
  }

  if (!lines || lines.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-foreground-muted gap-2 py-16">
        <Mic2 className="w-10 h-10 opacity-40 text-primary" />
        <p className="text-sm">No lyrics found for this track.</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col relative select-none">
      {/* Provider badge */}
      {lyrics?.provider && (
        <div className="flex items-center justify-between px-6 py-3 border-b border-border/40 shrink-0">
          <div className="flex items-center gap-1.5 text-xs text-foreground-muted font-medium">
            <Sparkles className="w-3.5 h-3.5 text-primary" />
            <span>Synced Lyrics</span>
          </div>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-semibold border border-primary/20">
            {lyrics.provider}
          </span>
        </div>
      )}

      {/* Lyrics Auto-scrolling List */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto px-6 py-12 space-y-6 text-center scroll-smooth"
      >
        {lines.map((line, idx) => {
          const isActive = idx === activeIndex;
          const isPassed = idx < activeIndex;

          return (
            <div
              key={idx}
              ref={isActive ? activeLineRef : null}
              onClick={() => seek(line.time)}
              className={`cursor-pointer transition-all duration-300 py-1.5 px-3 rounded-2xl ${
                isActive
                  ? 'text-white text-2xl md:text-3xl font-extrabold scale-105 tracking-tight'
                  : isPassed
                  ? 'text-foreground-muted/50 text-lg md:text-xl font-medium hover:text-foreground-muted'
                  : 'text-foreground-subtle text-lg md:text-xl font-medium hover:text-foreground'
              }`}
              style={{
                textShadow: isActive ? '0 0 25px rgba(250, 45, 72, 0.45)' : 'none',
              }}
            >
              {/* If syllable / word level timings are present */}
              {line.words && line.words.length > 0 ? (
                <div className="flex flex-wrap justify-center gap-x-1.5">
                  {line.words.map((word, wIdx) => {
                    const isWordActive = currentTime >= word.time;
                    return (
                      <span
                        key={wIdx}
                        className={`transition-all duration-150 ${
                          isWordActive
                            ? 'text-white font-extrabold'
                            : 'text-foreground-muted/40 font-semibold'
                        }`}
                      >
                        {word.text}
                      </span>
                    );
                  })}
                </div>
              ) : (
                <span>{line.text}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
