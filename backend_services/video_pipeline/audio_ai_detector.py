"""
ViFake Analytics - AI Voice Clone Detection

Detects AI-generated voices using MFCC features and spectrogram analysis.
Implements lightweight classifiers optimized for Render.com free tier.
"""

import asyncio
import logging
import numpy as np
import librosa
from typing import Dict, Optional, Tuple
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

class AudioAIDetector:
    """Detect AI-generated voices using audio analysis"""
    
    def __init__(self):
        self.sample_rate = 16000  # Standard for voice analysis
        self.n_mfcc = 13  # Standard MFCC features
        self.n_fft = 2048
        self.hop_length = 512
        
        # Initialize simple classifier (will be trained/loaded)
        self.classifier = None
        self._load_models()
    
    def _load_models(self):
        """Load pre-trained models or create fallback"""
        try:
            # Try to load pre-trained model if available
            # For now, create a simple rule-based detector
            self.classifier = self._create_rule_based_detector()
            logger.info("✅ Audio AI detector loaded (rule-based)")
        except Exception as e:
            logger.error(f"❌ Failed to load audio AI models: {e}")
            self.classifier = None
    
    def _create_rule_based_detector(self):
        """Create simple rule-based AI voice detector"""
        # This is a placeholder implementation
        # In production, replace with trained model from ASVspoof dataset
        return {
            'breath_threshold': 0.3,  # Threshold for breath noise detection
            'prosody_threshold': 0.7,  # Threshold for unnatural prosody
            'frequency_threshold': 0.6,  # Threshold for overly clean frequency response
        }
    
    async def analyze_audio(self, audio_path: str) -> Dict:
        """
        Analyze audio file to detect AI-generated voice
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Dict with AI confidence and features
        """
        try:
            # Load audio
            y, sr = librosa.load(audio_path, sr=self.sample_rate)
            
            # Extract features
            features = await self._extract_features(y, sr)
            
            # Detect AI voice
            ai_confidence = self._detect_ai_voice(features)
            
            return {
                'is_ai_voice': ai_confidence > 0.5,
                'ai_confidence': float(ai_confidence),
                'features': features,
                'analysis_type': 'mfcc_spectrogram'
            }
            
        except Exception as e:
            logger.error(f"❌ Audio AI analysis failed: {e}")
            return {
                'is_ai_voice': False,
                'ai_confidence': 0.0,
                'features': {},
                'analysis_type': 'error',
                'error': str(e)
            }
    
    async def _extract_features(self, y: np.ndarray, sr: int) -> Dict:
        """Extract MFCC and spectrogram features"""
        loop = asyncio.get_event_loop()
        
        # Run heavy processing in executor
        features = await loop.run_in_executor(
            None,
            self._compute_features,
            y, sr
        )
        
        return features
    
    def _compute_features(self, y: np.ndarray, sr: int) -> Dict:
        """Compute audio features for AI detection"""
        features = {}
        
        # 1. MFCC features
        mfcc = librosa.feature.mfcc(
            y=y, 
            sr=sr, 
            n_mfcc=self.n_mfcc,
            n_fft=self.n_fft,
            hop_length=self.hop_length
        )
        
        # MFCC statistics
        features['mfcc_mean'] = np.mean(mfcc, axis=1)
        features['mfcc_std'] = np.std(mfcc, axis=1)
        features['mfcc_delta'] = np.mean(np.diff(mfcc, axis=1), axis=1)
        
        # 2. Spectral features
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)
        features['spectral_centroid_mean'] = np.mean(spectral_centroids)
        features['spectral_centroid_std'] = np.std(spectral_centroids)
        
        # 3. Zero crossing rate (breath noise indicator)
        zcr = librosa.feature.zero_crossing_rate(y)
        features['zcr_mean'] = np.mean(zcr)
        features['zcr_std'] = np.std(zcr)
        
        # 4. Spectral flatness (indicator of "unnatural" clean audio)
        spectral_flatness = librosa.feature.spectral_flatness(y=y)
        features['spectral_flatness_mean'] = np.mean(spectral_flatness)
        features['spectral_flatness_std'] = np.std(spectral_flatness)
        
        # 5. RMS energy (prosody analysis)
        rms = librosa.feature.rms(y=y)
        features['rms_mean'] = np.mean(rms)
        features['rms_std'] = np.std(rms)
        features['rms_dynamic_range'] = np.max(rms) - np.min(rms)
        
        # 6. Mel-spectrogram for frequency analysis
        mel_spec = librosa.feature.melspectrogram(
            y=y, 
            sr=sr, 
            n_mels=64,
            fmin=20, 
            fmax=8000  # Focus on voice range
        )
        
        # Analyze frequency bands (4-8kHz for AI artifacts)
        freq_bands = librosa.feature.melspectrogram(
            y=y, 
            sr=sr, 
            n_mels=64,
            fmin=4000, 
            fmax=8000
        )
        features['high_freq_energy'] = np.mean(freq_bands)
        features['high_freq_ratio'] = features['high_freq_energy'] / np.mean(mel_spec)
        
        return features
    
    def _detect_ai_voice(self, features: Dict) -> float:
        """
        Detect AI voice using rule-based approach
        
        Placeholder for ML model - replace with trained classifier
        """
        if self.classifier is None:
            return 0.0
        
        # Rule-based detection based on audio characteristics
        ai_indicators = []
        
        # 1. Low zero crossing rate (less breath noise)
        zcr_score = 1.0 - min(features['zcr_mean'] / 0.1, 1.0)
        ai_indicators.append(zcr_score * 0.3)
        
        # 2. High spectral flatness (unnaturally clean)
        flatness_score = min(features['spectral_flatness_mean'] / 0.5, 1.0)
        ai_indicators.append(flatness_score * 0.2)
        
        # 3. Low RMS dynamic range (unnatural prosody)
        dynamic_score = 1.0 - min(features['rms_dynamic_range'] / 0.1, 1.0)
        ai_indicators.append(dynamic_score * 0.3)
        
        # 4. High frequency ratio (overly clean 4-8kHz)
        freq_score = min(features['high_freq_ratio'] / 0.3, 1.0)
        ai_indicators.append(freq_score * 0.2)
        
        # Combine scores
        ai_confidence = np.mean(ai_indicators)
        
        # Apply threshold smoothing
        ai_confidence = max(0.0, min(1.0, ai_confidence))
        
        logger.debug(f"AI Voice indicators: ZCR={zcr_score:.3f}, "
                   f"Flatness={flatness_score:.3f}, "
                   f"Dynamic={dynamic_score:.3f}, "
                   f"Freq={freq_score:.3f}, "
                   f"Final={ai_confidence:.3f}")
        
        return ai_confidence
    
    def _analyze_breath_patterns(self, y: np.ndarray, sr: int) -> float:
        """Analyze breath patterns between speech segments"""
        # Detect speech segments
        intervals = librosa.effects.split(y, top_db=20)
        
        if len(intervals) < 2:
            return 0.5  # No clear segments
        
        # Analyze gaps between segments (potential breaths)
        breath_indicators = []
        for i in range(len(intervals) - 1):
            gap_start = intervals[i][1]
            gap_end = intervals[i + 1][0]
            
            if gap_end - gap_start > 1000:  # Gap > 1ms
                gap_audio = y[gap_start:gap_end]
                gap_energy = np.mean(gap_audio ** 2)
                breath_indicators.append(gap_energy)
        
        # Low energy in gaps = missing breath noise
        if not breath_indicators:
            return 0.8  # No gaps detected
        
        avg_breath_energy = np.mean(breath_indicators)
        return 1.0 - min(avg_breath_energy / 0.001, 1.0)
    
    def _analyze_prosody(self, y: np.ndarray, sr: int) -> float:
        """Analyze prosody for unnatural regularity"""
        # Extract pitch contour
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr, threshold=0.1)
        
        # Get dominant pitch for each frame
        pitch_contour = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            pitch_contour.append(pitch)
        
        pitch_contour = np.array(pitch_contour)
        pitch_contour = pitch_contour[pitch_contour > 0]  # Remove unvoiced frames
        
        if len(pitch_contour) < 10:
            return 0.5  # Not enough pitch data
        
        # Analyze pitch variation (low variation = unnatural)
        pitch_std = np.std(pitch_contour)
        pitch_range = np.max(pitch_contour) - np.min(pitch_contour)
        
        # Normalize and invert (less variation = more AI-like)
        variation_score = 1.0 - min(pitch_std / 50, 1.0)
        range_score = 1.0 - min(pitch_range / 200, 1.0)
        
        return (variation_score + range_score) / 2
