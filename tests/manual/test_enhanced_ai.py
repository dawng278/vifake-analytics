#!/usr/bin/env python3
"""
Test Enhanced AI Detection Pipeline

Tests the new 60/40 weighted fusion with:
- AI Voice Clone Detection (Audio)
- AI Avatar Detection (Vision with face cropping)
- Enhanced fusion logic with high-confidence rules
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend_services.video_pipeline.pipeline_coordinator import VideoAnalysisPipeline

async def test_enhanced_ai_detection():
    """Test enhanced AI detection with sample video URLs"""
    
    # Test cases with expected AI indicators
    test_cases = [
        {
            "name": "Real Human Video",
            "url": "https://v16-web.tiktokcdn.com/share/video/real_human_123.mp4",
            "description": "Check out this amazing dance!",
            "author": "real_user",
            "expected_ai_voice": False,
            "expected_ai_face": False,
            "expected_verdict": "SAFE"
        },
        {
            "name": "AI Avatar Video",
            "url": "https://v16-web.tiktokcdn.com/share/video/ai_avatar_456.mp4", 
            "description": "AI generated content test",
            "author": "ai_avatar_bot",
            "expected_ai_voice": True,
            "expected_ai_face": True,
            "expected_verdict": "SUSPICIOUS"
        },
        {
            "name": "AI Voice Clone",
            "url": "https://v16-web.tiktokcdn.com/share/video/ai_voice_789.mp4",
            "description": "Listen to this perfect voice",
            "author": "voice_clone_bot", 
            "expected_ai_voice": True,
            "expected_ai_face": False,
            "expected_verdict": "SUSPICIOUS"
        }
    ]
    
    pipeline = VideoAnalysisPipeline()
    
    print("🧪 Testing Enhanced AI Detection Pipeline")
    print("=" * 60)
    print("Features:")
    print("  🎤 AI Voice Clone Detection (MFCC + Spectrogram)")
    print("  🎭 AI Avatar Detection (EfficientNet-B4 + Face Cropping)")
    print("  ⚖️  60/40 Weighted Fusion (Vision 60%, Audio 40%)")
    print("  🚨 High-Confidence Rules (>0.85)")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📹 Test {i}: {test_case['name']}")
        print(f"   URL: {test_case['url']}")
        print(f"   Expected AI Voice: {test_case['expected_ai_voice']}")
        print(f"   Expected AI Face: {test_case['expected_ai_face']}")
        print(f"   Expected Verdict: {test_case['expected_verdict']}")
        
        try:
            result = await pipeline.run(
                video_url=test_case['url'],
                description=test_case['description'],
                author=test_case['author']
            )
            
            # Basic results
            print(f"   ✅ Verdict: {result['verdict']}")
            print(f"   📊 Overall Confidence: {result['confidence']:.3f}")
            print(f"   ⏱️  Processing: {result.get('processing_ms', 0)}ms")
            
            # AI Detection Results
            print(f"   🤖 AI Generated: {result['is_ai_generated']}")
            print(f"   📈 Weighted AI Score: {result.get('ai_confidence', 0):.3f}")
            
            # Individual AI scores
            vision_conf = result.get('ai_vision_confidence', 0)
            audio_conf = result.get('ai_audio_confidence', 0)
            print(f"   👁 Vision AI: {vision_conf:.3f}")
            print(f"   🎤 Audio AI: {audio_conf:.3f}")
            
            # High-confidence flag
            high_conf = result.get('high_confidence_flag', False)
            print(f"   🚨 High Confidence: {high_conf}")
            
            # Face detection info
            faces_detected = result.get('vision_faces_detected', 0)
            primary_method = result.get('vision_primary_method', 'unknown')
            print(f"   👥 Faces Detected: {faces_detected}")
            print(f"   🔍 Primary Method: {primary_method}")
            
            # Audio AI info
            audio_ai_detected = result.get('audio_ai_detected', False)
            print(f"   🎤 AI Voice Detected: {audio_ai_detected}")
            
            # Verification
            verdict_match = result['verdict'] == test_case['expected_verdict']
            ai_voice_match = audio_ai_detected == test_case['expected_ai_voice']
            ai_face_match = result['is_ai_generated'] == test_case['expected_ai_face']
            
            print(f"   🔍 Verdict Match: {verdict_match} ✅" if verdict_match else f"   🔍 Verdict Match: {verdict_match} ❌")
            print(f"   🎤 AI Voice Match: {ai_voice_match} ✅" if ai_voice_match else f"   🎤 AI Voice Match: {ai_voice_match} ❌")
            print(f"   👁 AI Face Match: {ai_face_match} ✅" if ai_face_match else f"   👁 AI Face Match: {ai_face_match} ❌")
            
            # Explanation
            explanation = result.get('explanation', '')
            if explanation:
                print(f"   📝 Explanation: {explanation}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("🎯 Enhanced AI Detection Test completed!")
    
    print("\n📊 Test Summary:")
    print("  - Audio AI Detection: MFCC + spectrogram analysis")
    print("  - Vision AI Detection: Face cropping + EfficientNet-B4")
    print("  - Fusion Logic: 60/40 weighting with high-confidence rules")
    print("  - Backward Compatibility: Maintains existing CLIP fallback")

if __name__ == "__main__":
    asyncio.run(test_enhanced_ai_detection())
