"""
ViFake Analytics - Audio Transcription with Whisper

Handles transcription of TikTok video audio to Vietnamese text
using OpenAI's Whisper model for speech recognition.
"""

import whisper
import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Load model once at startup to avoid repeated loading
_whisper_model = None

def get_whisper_model():
    """Get or create Whisper model instance"""
    global _whisper_model
    if _whisper_model is None:
        logger.info("🎵 Loading Whisper base model...")
        _whisper_model = whisper.load_model("base")
        logger.info("✅ Whisper model loaded successfully")
    return _whisper_model

class Transcriber:
    """Transcribe audio files to Vietnamese text"""
    
    def __init__(self):
        self.model = None  # Will be loaded on first use
    
    async def transcribe(self, audio_path: str) -> Dict:
        """
        Transcribe audio file to text.
        Runs in executor since Whisper is blocking CPU operation.
        
        Args:
            audio_path: Path to audio file (MP3, M4A, etc.)
            
        Returns:
            Dict with transcript, language, and segments
        """
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._run_whisper,
                audio_path
            )
            
            logger.info(f"🎯 Transcription completed: {len(result['text'])} characters")
            return result
            
        except Exception as e:
            logger.error(f"❌ Transcription failed: {e}")
            # Return empty result instead of raising to allow pipeline to continue
            return {
                "text": "",
                "language": "vi",
                "segments": [],
                "error": str(e)
            }
    
    def _run_whisper(self, audio_path: str) -> Dict:
        """Run Whisper model on audio file"""
        model = get_whisper_model()
        
        result = model.transcribe(
            audio_path,
            language="vi",           # Force Vietnamese - faster than auto-detect
            task="transcribe",
            fp16=False,              # False if server doesn't have GPU
            verbose=False,
            # Additional options for better Vietnamese recognition
            temperature=0.0,        # Lower temperature for more deterministic output
            best_of=1,              # No beam search for speed
            beam_size=1,             # Simple decoding
        )
        
        # Process segments for timing information
        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip()
            })
        
        return {
            "text": result["text"].strip(),
            "language": result.get("language", "vi"),
            "segments": segments
        }
    
    def build_analysis_text(self, transcript: str, description: str, author: str) -> str:
        """
        Combine all text sources for analysis.
        TikTok captions often contain important hashtags and scam keywords.
        """
        parts = []
        
        if description and len(description.strip()) > 0:
            parts.append(f"[Mô tả]: {description.strip()}")
        
        if transcript and len(transcript.strip()) > 0:
            parts.append(f"[Nội dung video]: {transcript.strip()}")
        
        if author and len(author.strip()) > 0:
            parts.append(f"[Tác giả]: {author.strip()}")
        
        combined_text = "\n".join(parts)
        logger.info(f"📝 Built analysis text: {len(combined_text)} characters from {len(parts)} sources")
        
        return combined_text
    
    def is_meaningful_transcript(self, transcript: str) -> bool:
        """
        Check if transcript contains meaningful content.
        Filters out music-only videos or failed transcriptions.
        """
        if not transcript or len(transcript.strip()) < 5:
            return False
        
        # Common indicators of non-speech content
        non_speech_indicators = [
            "♪", "♫", "♬", "♩",  # Music notes
            "(music)", "(instrumental)",
            "đang phát nhạc", "nhạc nền",
            "no speech", "instrumental"
        ]
        
        transcript_lower = transcript.lower()
        for indicator in non_speech_indicators:
            if indicator in transcript_lower:
                return False
        
        # Check if there are actual Vietnamese words
        vietnamese_chars = set("àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ")
        has_vietnamese = any(char in vietnamese_chars for char in transcript)
        
        return has_vietnamese
