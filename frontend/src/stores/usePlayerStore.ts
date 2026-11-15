import { create } from 'zustand';
import { Track, SponsorBlockSegment, LyricsResponse } from '../types';
import { api } from '../services/api';

export const EQ_FREQUENCIES = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000];

export const EQ_PRESETS: Record<string, number[]> = {
  Flat: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  'Bass Boost': [6, 5, 4, 2, 0, 0, 0, 1, 2, 3],
  'Vocal Booster': [-2, -1, 0, 2, 4, 4, 3, 1, 0, -1],
  Rock: [4, 3, 2, 0, -1, 0, 2, 3, 4, 4],
  Electronic: [5, 4, 2, 0, -2, 2, 1, 2, 4, 4],
  'Hip Hop': [6, 5, 2, 1, -1, -1, 1, 0, 2, 3],
  Acoustic: [3, 2, 1, 1, 2, 2, 3, 3, 3, 2],
  Classical: [4, 3, 2, 2, -1, -1, 0, 2, 3, 3],
  Pop: [-1, 1, 3, 4, 4, 2, -1, -1, 2, 3],
};

interface AudioStats {
  codec: string;
  bitrate: number;
  duration: number;
  provider: string;
}

interface PlayerState {
  currentTrack: Track | null;
  queue: Track[];
  queueIndex: number;
  isPlaying: boolean;
  isLoading: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  playbackSpeed: number;
  shuffle: boolean;
  repeatMode: 'off' | 'all' | 'one';
  crossfadeSeconds: number;
  sponsorBlockEnabled: boolean;
  skipSegments: SponsorBlockSegment[];
  lastSkippedNotice: string | null;
  lyrics: LyricsResponse | null;
  isLyricsLoading: boolean;

  // Equalizer
  eqEnabled: boolean;
  eqPreset: string;
  eqBands: number[]; // 10 gain values (-12 to +12 dB)

  // Modals & Panels
  isExpanded: boolean;
  isVideoMode: boolean;
  isLyricsOpen: boolean;
  isEqualizerOpen: boolean;
  isQueueOpen: boolean;
  showStatsForNerds: boolean;
  audioStats: AudioStats | null;

  // Actions
  playTrack: (track: Track, newQueue?: Track[]) => Promise<void>;
  togglePlay: () => void;
  next: () => Promise<void>;
  previous: () => Promise<void>;
  seek: (seconds: number) => void;
  setVolume: (volume: number) => void;
  toggleMute: () => void;
  setPlaybackSpeed: (speed: number) => void;
  toggleShuffle: () => void;
  cycleRepeat: () => void;
  setCrossfade: (seconds: number) => void;
  setEqBand: (index: number, gain: number) => void;
  setEqPreset: (presetName: string) => void;
  toggleEq: () => void;
  setExpanded: (expanded: boolean) => void;
  setVideoMode: (video: boolean) => void;
  toggleLyrics: () => void;
  toggleEqualizer: () => void;
  toggleQueue: () => void;
  toggleStatsForNerds: () => void;
  addToQueue: (track: Track) => void;
  removeFromQueue: (index: number) => void;
  clearQueue: () => void;
  loadLyrics: (track: Track) => Promise<void>;
}

// Global Audio Element and Web Audio Context
let audioElement: HTMLAudioElement | null = null;
let audioContext: AudioContext | null = null;
let sourceNode: MediaElementAudioSourceNode | null = null;
let eqFilterNodes: BiquadFilterNode[] = [];
let gainNode: GainNode | null = null;

function initAudioEngine(state: PlayerState) {
  if (audioElement) return;

  audioElement = new Audio();
  audioElement.crossOrigin = 'anonymous';
  audioElement.preload = 'auto';

  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    if (AudioCtx) {
      audioContext = new AudioCtx();
      sourceNode = audioContext.createMediaElementSource(audioElement);
      gainNode = audioContext.createGain();

      // Build 10-band graphic equalizer
      eqFilterNodes = EQ_FREQUENCIES.map((freq, i) => {
        const filter = audioContext!.createBiquadFilter();
        if (i === 0) {
          filter.type = 'lowshelf';
        } else if (i === EQ_FREQUENCIES.length - 1) {
          filter.type = 'highshelf';
        } else {
          filter.type = 'peaking';
          filter.Q.value = 1.4;
        }
        filter.frequency.value = freq;
        filter.gain.value = state.eqBands[i] || 0;
        return filter;
      });

      // Chain: source -> eq[0] -> eq[1] ... -> gain -> destination
      let lastNode: AudioNode = sourceNode;
      for (const filter of eqFilterNodes) {
        lastNode.connect(filter);
        lastNode = filter;
      }
      lastNode.connect(gainNode);
      gainNode.connect(audioContext.destination);
    }
  } catch (err) {
    console.warn('Web Audio API EQ not available, falling back to direct playback', err);
  }

  // Audio Event Listeners
  audioElement.addEventListener('timeupdate', () => {
    if (!audioElement) return;
    const time = audioElement.currentTime;
    usePlayerStore.setState({ currentTime: time });

    // Check SponsorBlock skip segments
    const { sponsorBlockEnabled, skipSegments } = usePlayerStore.getState();
    if (sponsorBlockEnabled && skipSegments.length > 0) {
      for (const seg of skipSegments) {
        if (time >= seg.start && time < seg.end - 0.5) {
          audioElement.currentTime = seg.end;
          usePlayerStore.setState({
            lastSkippedNotice: `Auto-skipped ${seg.category.replace('_', ' ')}`,
          });
          setTimeout(() => {
            usePlayerStore.setState({ lastSkippedNotice: null });
          }, 3000);
          break;
        }
      }
    }
  });

  audioElement.addEventListener('loadedmetadata', () => {
    if (audioElement) {
      usePlayerStore.setState({ duration: audioElement.duration || 0, isLoading: false });
    }
  });

  audioElement.addEventListener('ended', () => {
    const { repeatMode, next } = usePlayerStore.getState();
    if (repeatMode === 'one' && audioElement) {
      audioElement.currentTime = 0;
      audioElement.play();
    } else {
      next();
    }
  });

  audioElement.addEventListener('waiting', () => {
    usePlayerStore.setState({ isLoading: true });
  });

  audioElement.addEventListener('playing', () => {
    usePlayerStore.setState({ isPlaying: true, isLoading: false });
  });

  audioElement.addEventListener('pause', () => {
    usePlayerStore.setState({ isPlaying: false });
  });
}

export const usePlayerStore = create<PlayerState>((set, get) => ({
  currentTrack: null,
  queue: [],
  queueIndex: -1,
  isPlaying: false,
  isLoading: false,
  currentTime: 0,
  duration: 0,
  volume: 0.85,
  isMuted: false,
  playbackSpeed: 1.0,
  shuffle: false,
  repeatMode: 'off',
  crossfadeSeconds: 3,
  sponsorBlockEnabled: true,
  skipSegments: [],
  lastSkippedNotice: null,
  lyrics: null,
  isLyricsLoading: false,

  eqEnabled: true,
  eqPreset: 'Flat',
  eqBands: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],

  isExpanded: false,
  isVideoMode: false,
  isLyricsOpen: false,
  isEqualizerOpen: false,
  isQueueOpen: false,
  showStatsForNerds: false,
  audioStats: null,

  playTrack: async (track: Track, newQueue?: Track[]) => {
    initAudioEngine(get());

    let queue = get().queue;
    let queueIndex = get().queueIndex;

    if (newQueue) {
      queue = newQueue;
      queueIndex = newQueue.findIndex((t) => t.id === track.id);
      if (queueIndex === -1) {
        queue = [track, ...newQueue];
        queueIndex = 0;
      }
    } else {
      const idx = queue.findIndex((t) => t.id === track.id);
      if (idx !== -1) {
        queueIndex = idx;
      } else {
        queue = [...queue, track];
        queueIndex = queue.length - 1;
      }
    }

    set({
      currentTrack: track,
      queue,
      queueIndex,
      isLoading: true,
      currentTime: 0,
      skipSegments: [],
      lyrics: null,
    });

    // Resume AudioContext if suspended
    if (audioContext && audioContext.state === 'suspended') {
      audioContext.resume();
    }

    try {
      let streamUrl = '';
      let codec = 'opus';
      let bitrate = 160;

      if (track.isLocal && track.filePath) {
        streamUrl = `http://127.0.0.1:47892/api/library/stream?path=${encodeURIComponent(track.filePath)}`;
        codec = track.filePath.split('.').pop() || 'mp3';
        set({
          audioStats: {
            codec,
            bitrate,
            duration: track.durationSeconds || 0,
            provider: 'Local Storage',
          },
        });
      } else {
        const videoId = track.videoId || track.id;
        // Use local range-aware audio streaming proxy to completely eliminate CORS restrictions
        streamUrl = `http://127.0.0.1:47892/api/stream/${encodeURIComponent(videoId)}/audio`;

        // Fetch stream metadata in background
        api.getAudioStream(videoId).then((streamInfo) => {
          set({
            audioStats: {
              codec: streamInfo.codec,
              bitrate: streamInfo.bitrate,
              duration: track.durationSeconds || streamInfo.duration || 0,
              provider: 'InnerTube Audio Proxy',
            },
          });
        }).catch(() => {});

        // Fetch SponsorBlock skip segments in background
        api.getSkipSegments(videoId).then((segs) => {
          set({ skipSegments: segs || [] });
        }).catch(() => {});
      }

      if (audioElement) {
        audioElement.src = streamUrl;
        audioElement.playbackRate = get().playbackSpeed;
        audioElement.volume = get().isMuted ? 0 : get().volume;
        try {
          await audioElement.play();
          set({ isPlaying: true, isLoading: false });
        } catch (playErr) {
          console.warn('Playback deferred or blocked by browser autoplay policy', playErr);
          set({ isPlaying: false, isLoading: false });
        }
      }

      // Fetch Lyrics in background
      get().loadLyrics(track);

      // Auto radio recommendation if queue is nearing end
      if (queueIndex >= queue.length - 2 && !track.isLocal) {
        api.getRadio(track.videoId || track.id).then((radioTracks) => {
          if (radioTracks && radioTracks.length > 0) {
            const currentQ = get().queue;
            const existingIds = new Set(currentQ.map((t) => t.id));
            const fresh = radioTracks.filter((t) => !existingIds.has(t.id));
            set({ queue: [...currentQ, ...fresh] });
          }
        }).catch(() => {});
      }
    } catch (err) {
      console.error('Failed to play track', err);
      set({ isLoading: false, isPlaying: false });
    }
  },

  togglePlay: () => {
    initAudioEngine(get());
    if (!audioElement || !get().currentTrack) return;
    if (audioContext && audioContext.state === 'suspended') {
      audioContext.resume();
    }
    if (audioElement.paused) {
      audioElement.play();
      set({ isPlaying: true });
    } else {
      audioElement.pause();
      set({ isPlaying: false });
    }
  },

  next: async () => {
    const { queue, queueIndex, shuffle, repeatMode } = get();
    if (queue.length === 0) return;

    let nextIndex = queueIndex + 1;
    if (shuffle) {
      nextIndex = Math.floor(Math.random() * queue.length);
    } else if (nextIndex >= queue.length) {
      if (repeatMode === 'all') {
        nextIndex = 0;
      } else {
        return;
      }
    }

    const nextTrack = queue[nextIndex];
    if (nextTrack) {
      await get().playTrack(nextTrack);
    }
  },

  previous: async () => {
    const { queue, queueIndex, currentTime } = get();
    if (currentTime > 3 && audioElement) {
      audioElement.currentTime = 0;
      set({ currentTime: 0 });
      return;
    }

    if (queue.length === 0 || queueIndex <= 0) return;
    const prevTrack = queue[queueIndex - 1];
    if (prevTrack) {
      await get().playTrack(prevTrack);
    }
  },

  seek: (seconds: number) => {
    if (audioElement) {
      audioElement.currentTime = seconds;
      set({ currentTime: seconds });
    }
  },

  setVolume: (val: number) => {
    const clamped = Math.max(0, Math.min(1, val));
    if (audioElement) {
      audioElement.volume = clamped;
    }
    set({ volume: clamped, isMuted: clamped === 0 });
  },

  toggleMute: () => {
    const { isMuted, volume } = get();
    if (audioElement) {
      audioElement.volume = isMuted ? volume : 0;
    }
    set({ isMuted: !isMuted });
  },

  setPlaybackSpeed: (speed: number) => {
    if (audioElement) {
      audioElement.playbackRate = speed;
    }
    set({ playbackSpeed: speed });
  },

  toggleShuffle: () => {
    set((s) => ({ shuffle: !s.shuffle }));
  },

  cycleRepeat: () => {
    const modes: ('off' | 'all' | 'one')[] = ['off', 'all', 'one'];
    const current = get().repeatMode;
    const nextMode = modes[(modes.indexOf(current) + 1) % modes.length];
    set({ repeatMode: nextMode });
  },

  setCrossfade: (seconds: number) => {
    set({ crossfadeSeconds: Math.max(0, Math.min(12, seconds)) });
    api.updateConfig({ crossfade_seconds: seconds }).catch(() => {});
  },

  setEqBand: (index: number, gain: number) => {
    const bands = [...get().eqBands];
    bands[index] = gain;
    if (eqFilterNodes[index]) {
      eqFilterNodes[index].gain.value = gain;
    }
    set({ eqBands: bands, eqPreset: 'Custom' });
  },

  setEqPreset: (presetName: string) => {
    const preset = EQ_PRESETS[presetName];
    if (!preset) return;
    preset.forEach((gain, i) => {
      if (eqFilterNodes[i]) {
        eqFilterNodes[i].gain.value = gain;
      }
    });
    set({ eqPreset: presetName, eqBands: [...preset] });
  },

  toggleEq: () => {
    const enabled = !get().eqEnabled;
    eqFilterNodes.forEach((filter, i) => {
      filter.gain.value = enabled ? get().eqBands[i] : 0;
    });
    set({ eqEnabled: enabled });
  },

  setExpanded: (expanded: boolean) => set({ isExpanded: expanded }),
  setVideoMode: (video: boolean) => set({ isVideoMode: video }),
  toggleLyrics: () => set((s) => ({ isLyricsOpen: !s.isLyricsOpen })),
  toggleEqualizer: () => set((s) => ({ isEqualizerOpen: !s.isEqualizerOpen })),
  toggleQueue: () => set((s) => ({ isQueueOpen: !s.isQueueOpen })),
  toggleStatsForNerds: () => set((s) => ({ showStatsForNerds: !s.showStatsForNerds })),

  addToQueue: (track: Track) => {
    set((s) => ({ queue: [...s.queue, track] }));
  },

  removeFromQueue: (index: number) => {
    const q = [...get().queue];
    q.splice(index, 1);
    set({ queue: q });
  },

  clearQueue: () => {
    const current = get().currentTrack;
    set({ queue: current ? [current] : [], queueIndex: current ? 0 : -1 });
  },

  loadLyrics: async (track: Track) => {
    set({ isLyricsLoading: true });
    try {
      const res = await api.getLyrics(track.title, track.artist, track.durationSeconds || 0);
      set({ lyrics: res, isLyricsLoading: false });
    } catch {
      set({ lyrics: null, isLyricsLoading: false });
    }
  },
}));
