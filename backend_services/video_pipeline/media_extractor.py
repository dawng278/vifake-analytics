"""
ViFake Analytics - Media Extractor for TikTok Videos

Handles extraction of audio and frames from TikTok video URLs
using yt-dlp and ffmpeg for processing.
"""

import asyncio
import uuid
import os
import re
import yt_dlp
import logging
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

TEMP_DIR = "/tmp/vifake_cache"

class MediaExtractor:
    """Extract audio and frames from TikTok video URLs"""
    
    def __init__(self, video_url: str):
        self.video_url = video_url
        self.session_id = str(uuid.uuid4())[:8]  # Unique ID per analysis
        self.session_dir = os.path.join(TEMP_DIR, self.session_id)
        self._stream_url_cache = None
        os.makedirs(self.session_dir, exist_ok=True)
        logger.info(f"🎬 MediaExtractor initialized for session {self.session_id}")

    async def extract_audio(self) -> str:
        """
        Extract audio only from video file.
        Returns path to MP3 file.
        Estimated size: 1-3MB for 1-minute video.
        """
        output_path = os.path.join(self.session_dir, "audio.mp3")
        
        ydl_opts = {
            "format": "bestaudio/best",        # Audio track only
            "outtmpl": output_path.replace(".mp3", ".%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "64",      # 64kbps sufficient for speech
            }],
            "max_filesize": 10 * 1024 * 1024,  # 10MB hard limit
            "socket_timeout": 15,
            "quiet": True,
            "no_warnings": True,
            # Simulate browser to avoid blocks
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
        }
        
        try:
            # Run yt-dlp in thread pool (blocking I/O)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._run_ydl, ydl_opts)
            
            # yt-dlp may change extension - find actual file
            for ext in ["mp3", "m4a", "webm", "opus"]:
                candidate = output_path.replace(".mp3", f".{ext}")
                if os.path.exists(candidate):
                    logger.info(f"✅ Audio extracted: {candidate} ({os.path.getsize(candidate)} bytes)")
                    return candidate
            
            raise FileNotFoundError("Audio extraction failed - no output file found")
            
        except Exception as e:
            logger.error(f"❌ Audio extraction failed: {e}")
            raise

    async def extract_frames(self, num_frames: int = 8) -> List[str]:
        """
        Extract representative frames from video for AI analysis.
        Uses ffmpeg to seek to timestamps without downloading full video.
        Returns list of frame file paths.
        """
        frames_dir = os.path.join(self.session_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        try:
            input_source = await self._resolve_playable_stream_url()
            # Get video duration first
            duration = await self._get_video_duration()
            logger.info(f"📹 Video duration: {duration:.1f}s")
            
            # Calculate evenly spaced timestamps (skip 10% start/end to avoid fade)
            start = duration * 0.1
            end = duration * 0.9
            if end <= start:
                # Very short video - use middle frame
                timestamps = [duration / 2]
            else:
                timestamps = [
                    start + (end - start) * i / (num_frames - 1) 
                    for i in range(num_frames)
                ]
            
            frame_paths = []
            for i, ts in enumerate(timestamps):
                frame_path = os.path.join(frames_dir, f"frame_{i:02d}.jpg")
                
                # ffmpeg extract single frame at timestamp
                # -ss before -i: fast seek (doesn't decode full video)
                cmd = [
                    "ffmpeg", "-ss", str(ts),
                    "-i", input_source,        # Stream directly from resolved media URL
                    "-vframes", "1",           # Extract 1 frame only
                    "-q:v", "3",               # Quality 3 (1-31, lower=better)
                    "-y", frame_path,
                    "-loglevel", "quiet"
                ]
                
                proc = await asyncio.create_subprocess_exec(*cmd)
                await proc.wait()
                
                if os.path.exists(frame_path):
                    frame_paths.append(frame_path)
                    logger.debug(f"🖼️ Frame {i} extracted at {ts:.1f}s")
                else:
                    logger.warning(f"⚠️ Frame {i} extraction failed at {ts:.1f}s")
            
            logger.info(f"✅ Extracted {len(frame_paths)}/{num_frames} frames")
            return frame_paths
            
        except Exception as e:
            logger.error(f"❌ Frame extraction failed: {e}")
            raise

    async def _resolve_playable_stream_url(self) -> str:
        """
        Resolve a direct playable stream URL for ffmpeg frame extraction.
        - Keep direct media URLs as-is.
        - For page URLs (TikTok/YouTube/etc.), ask yt-dlp for best direct stream.
        """
        if self._stream_url_cache:
            return self._stream_url_cache

        # Already a direct media URL.
        if re.search(r'\.(mp4|webm|mov|m3u8)(\?|#|$)', self.video_url, re.IGNORECASE):
            self._stream_url_cache = self.video_url
            return self._stream_url_cache

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 15,
        }

        def resolve_url():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(self.video_url, download=False)
                    if not isinstance(info, dict):
                        return self.video_url
                    direct = info.get("url")
                    if direct:
                        return direct
                    formats = info.get("formats") or []
                    for fmt in formats:
                        if fmt.get("url") and fmt.get("vcodec") != "none":
                            return fmt["url"]
            except Exception as e:
                logger.warning(f"⚠️ Could not resolve direct stream URL, fallback to source URL: {e}")
            return self.video_url

        loop = asyncio.get_event_loop()
        self._stream_url_cache = await loop.run_in_executor(None, resolve_url)
        return self._stream_url_cache

    async def _get_video_duration(self) -> float:
        """Get video duration without downloading"""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,    # Metadata only
        }
        
        def get_info():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(self.video_url, download=False)
                    return info.get("duration", 60)  # Default 60s if not found
            except Exception as e:
                logger.warning(f"⚠️ Could not get video info: {e}")
                return 60  # Fallback duration
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, get_info)

    def _run_ydl(self, opts):
        """Run yt-dlp with given options"""
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([self.video_url])

    def get_session_info(self) -> dict:
        """Get session information for debugging"""
        return {
            "session_id": self.session_id,
            "session_dir": self.session_dir,
            "video_url": self.video_url,
            "temp_dir_exists": os.path.exists(self.session_dir)
        }
