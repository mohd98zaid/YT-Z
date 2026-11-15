# YT-Z: Ultimate YouTube Music Client & 4K Downloader

**YT-Z** is a unified desktop music player and media workstation that synthesizes the finest engineering and design achievements from three standout open-source projects:

1. **[ytm-rs](https://github.com/grapedjuice/ytm-rs)**: Fast lightweight YouTube Music architecture, 30+ aesthetic preset themes (Apple Music, Catppuccin, Tokyo Night, Nord, OLED Black, etc.), Spotify playlist migration, and SponsorBlock segment skipping.
2. **[BitChord](https://github.com/kushagrasinghx/BitChord)**: Apple Music-inspired frosted glass aesthetic, dynamic ambient artwork mesh backdrop, word-by-word synced karaoke lyrics engine with multi-provider fallbacks (LRCLIB, lrc.red, KuGou, Genius), 10-band hardware graphic equalizer, and gapless crossfade.
3. **[VideoDownloaderPython (StreamFlow Pro)](https://github.com/...)**: Industrial multi-threaded `yt-dlp` download engine with video up to 4K (2160p), audio up to 320kbps MP3 / lossless FLAC, automatic high-res thumbnail embedding, ID3 tagging, concurrent worker queue, and SQLite history database.

---

## 🌟 Key Features

### 🎵 1. Music Discovery & Playback Engine
- **Dynamic Home Feed**: Personalized quick picks, recommended for you, trending tracks, and community collections.
- **Top Charts**: Real-time rankings for Top Songs, Top Music Videos, and Top Artists.
- **Moods & Genres**: Instant categorization for Workout, Chill, Focus, Party, Romance, Sleep, and Energize with curated playlist feeds.
- **Comprehensive Search**: Autocomplete suggestions, filtered search across Songs, Videos, Albums, Artists, and Playlists.
- **Continuous Radio & Automix**: Automatically fetches Up Next recommendations to keep the music playing indefinitely.
- **Local Media Library**: Scan local downloaded files and music folders with ID3 tag extraction and in-app streaming.

### 🎨 2. Aesthetics & 30+ Theme Presets
- **Frosted Glass UI**: Translucent sidebars, floating docks, and full-bleed artwork displays.
- **Dynamic Ambient Canvas**: Extracts dominant color palettes from active album art into a blurred backdrop.
- **30 Built-in Preset Themes**:
  - *Apple*: Apple Music Dark, Apple Music Light
  - *Dark*: OLED Pure Black, Tokyo Night, Tokyo Night Storm, Nord Frost, Dracula, Rosé Pine, Gruvbox Dark, Windows 11 Mica / Fluent, Glassy Blur, Emerald Forest
  - *Catppuccin*: Mocha, Macchiato, Latte
  - *Vibrant*: Cyberpunk Neon, Synthwave 84, Lyric Glow, Material 3 Dynamic, Spinning Record

### 🎚️ 3. Studio Audio DSP & Playback Controls
- **10-Band Graphic Equalizer**: Web Audio hardware-accelerated biquad filters covering 32 Hz to 16 kHz with +/- 12 dB gain adjustment.
- **Studio EQ Presets**: Flat, Bass Boost, Vocal Booster, Rock, Pop, Electronic, Hip Hop, Acoustic, Classical.
- **Adjustable Crossfade**: Gapless playback with 0 to 12 second crossfade blending.
- **Variable Playback Speed**: 0.5x, 0.75x, 1.0x, 1.25x, 1.5x, 2.0x playback rate.
- **SponsorBlock Integration**: Automatically skips non-music video intros, outros, dialogue, and sponsorships.
- **Stats for Nerds Overlay**: Real-time display of audio codec (Opus/AAC), bitrate (kbps), stream origin, and buffer status.

### 🎤 4. Apple-Style Word-Synced Karaoke Lyrics
- **Cascading Multi-Provider Engine**:
  - **LRCLIB**: Open-source synchronized LRC lyrics.
  - **lrc.red**: Apple Music TTML syllable-level word timestamps.
  - **KuGou**: Extensive Asian & Western synced lyrics database.
  - **Genius**: Fallback verified plain lyrics.
- **Interactive Karaoke Display**:
  - Syllable / word-level glow animation.
  - Smooth auto-scrolling to the currently active lyric line.
  - **Click-to-Seek**: Click any lyric line to jump playback directly to that exact second.

### 📥 5. Industrial yt-dlp Downloader Workstation
- **Video Downloads**: 4K (2160p), 1440p, 1080p, 720p, 480p, 360p in MP4 or MKV containers.
- **Audio Extraction**: MP3 (320kbps, 256kbps, 192kbps), FLAC (Lossless), M4A (AAC), OPUS, WAV.
- **Metadata Tagging**: High-res thumbnail embedding, title, artist, album, year, and lyrics tagging via `mutagen` & `ffmpeg`.
- **Concurrent Queue**: Multi-threaded downloader with real-time download speed (MB/s), ETA, pause, cancel, and retry.
- **1-Click Player Download**: Download the currently playing song instantly in 320k MP3 directly from the mini-player.
- **Playlist Inspector**: Enter any playlist URL, preview tracks, select all or specific items, and batch download.
- **Windows Explorer Integration**: Open downloaded media files and destination folders directly in Windows Explorer.

### 🔄 6. Spotify Playlist Importer
- Paste any Spotify playlist, album, or track URL.
- Automatically extracts tracks and matches them against YouTube Music.
- One-click **"Play All"** to stream as a queue or **"Download All"** to batch queue 320k MP3s.

---

## 🏛️ Architecture Overview

```text
                                  YT-Z Architecture
                                  
     Frontend Desktop Client (React 19 + TypeScript + Vite + Tailwind CSS)
            │
            │ REST HTTP + Real-Time WebSocket (Port 47892)
            ▼
     FastAPI Core Engine (Python 3.10+) strictly bound to 127.0.0.1
            │
            ├── YTMusicService (InnerTube API / ytmusicapi)
            │     └── Home Feed, Charts, Moods, Search, Radio
            │
            ├── StreamResolver (Audio extraction + SponsorBlock)
            │     └── High-bitrate Opus (160k) / AAC (256k) googlevideo streams
            │
            ├── LyricsEngine (Multi-provider cascading resolver)
            │     └── LRCLIB, lrc.red (TTML), KuGou, Genius
            │
            ├── DownloaderEngine (Multi-threaded yt-dlp + ffmpeg + mutagen)
            │     └── 4K Video, 320k MP3/FLAC, metadata & cover embedding
            │
            ├── SpotifyImporter (Public embed parser + YTM track matcher)
            │
            ├── LocalLibrary (Local audio scanner & streaming bridge)
            │
            └── DatabaseManager (SQLite ~/.ytz/ytz.db)
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend development)
- Windows 10/11 (or macOS / Linux)

### Quick Launch (Windows)
Double-click `run.bat` or run:
```cmd
python main.py
```
This starts the local FastAPI core engine on `http://127.0.0.1:47892` and opens the native desktop client window!

### Development Mode
To develop the frontend with hot-module reload (HMR):
```bash
# Terminal 1: Start backend
python -m backend.server

# Terminal 2: Start frontend dev server
cd frontend
npm.cmd run dev
```

---

## 📄 License
This project is released under the MIT License.
