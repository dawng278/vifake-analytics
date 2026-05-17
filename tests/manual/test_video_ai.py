#!/usr/bin/env python3
"""
Test AI Video Detection Pipeline

Usage:
python tests/manual/test_video_ai.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend_services.video_pipeline.pipeline_coordinator import VideoAnalysisPipeline

async def test_ai_detection():
    """Test AI detection with sample video URLs"""
    
    # Sample TikTok video URLs (replace with real ones)
    test_cases = [
        {
            "name": "Real Human Video",
            "url": "https://v16-web.tiktokcdn.com/share/video/1234567890.mp4",  # Replace
            "description": "Check out this amazing dance!",
            "author": "real_user",
            "expected_ai": False
        },
        {
            "name": "AI Avatar Video", 
            "url": "https://v16-web.tiktokcdn.com/share/video/0987654321.mp4",  # Replace
            "description": "AI generated content test",
            "author": "ai_avatar_bot",
            "expected_ai": True
        }
    ]
    
    pipeline = VideoAnalysisPipeline()
    
    print("🧪 Testing AI Video Detection Pipeline")
    print("=" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📹 Test {i}: {test_case['name']}")
        print(f"   URL: {test_case['url']}")
        print(f"   Expected AI: {test_case['expected_ai']}")
        
        try:
            result = await pipeline.run(
                video_url=test_case['url'],
                description=test_case['description'],
                author=test_case['author']
            )
            
            print(f"   ✅ Verdict: {result['verdict']}")
            print(f"   🤖 AI Generated: {result['is_ai_generated']} ({result['ai_confidence']:.3f})")
            print(f"   📝 Confidence: {result['confidence']:.3f}")
            print(f"   ⏱️  Processing: {result['processing_ms']}ms")
            
            # Check if AI detection matches expectation
            ai_detected = result['is_ai_generated']
            if ai_detected == test_case['expected_ai']:
                print(f"   ✅ AI Detection: CORRECT")
            else:
                print(f"   ❌ AI Detection: WRONG (expected {test_case['expected_ai']}, got {ai_detected})")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Test completed!")

if __name__ == "__main__":
    asyncio.run(test_ai_detection())
