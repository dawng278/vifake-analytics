#!/usr/bin/env python3
"""
Test Video Analysis API Endpoint Directly

Usage:
python test_api_video.py
"""

import asyncio
import aiohttp
import json

async def test_video_api():
    """Test /api/v1/analyze/video endpoint"""
    
    # Test data
    test_payload = {
        "video_url": "https://v16-web.tiktokcdn.com/share/video/1234567890.mp4",
        "description": "Test video for AI detection",
        "author": "test_user",
        "page_url": "https://www.tiktok.com/@test/video/1234567890"
    }
    
    # API endpoints
    local_api = "http://localhost:8000/api/v1/analyze/video"
    remote_api = "https://vifake-analytics-api.onrender.com/api/v1/analyze/video"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer demo-token-123"
    }
    
    print("🧪 Testing Video Analysis API")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        # Test local API first
        print(f"\n📡 Testing Local API: {local_api}")
        try:
            async with session.post(local_api, headers=headers, json=test_payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"   ✅ Status: {resp.status}")
                    print(f"   🎯 Verdict: {result.get('verdict')}")
                    print(f"   🤖 AI Generated: {result.get('is_ai_generated')} ({result.get('ai_confidence', 0):.3f})")
                    print(f"   📝 Confidence: {result.get('confidence', 0):.3f}")
                    print(f"   ⏱️  Processing: {result.get('processing_ms', 0)}ms")
                    print(f"   📄 Transcript length: {len(result.get('transcript', ''))}")
                else:
                    error_text = await resp.text()
                    print(f"   ❌ Status: {resp.status}")
                    print(f"   ❌ Error: {error_text}")
        except Exception as e:
            print(f"   ❌ Connection Error: {e}")
        
        # Test remote API
        print(f"\n🌐 Testing Remote API: {remote_api}")
        try:
            async with session.post(remote_api, headers=headers, json=test_payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"   ✅ Status: {resp.status}")
                    print(f"   🎯 Verdict: {result.get('verdict')}")
                    print(f"   🤖 AI Generated: {result.get('is_ai_generated')} ({result.get('ai_confidence', 0):.3f})")
                    print(f"   📝 Confidence: {result.get('confidence', 0):.3f}")
                    print(f"   ⏱️  Processing: {result.get('processing_ms', 0)}ms")
                else:
                    error_text = await resp.text()
                    print(f"   ❌ Status: {resp.status}")
                    print(f"   ❌ Error: {error_text}")
        except Exception as e:
            print(f"   ❌ Connection Error: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 API Test completed!")

if __name__ == "__main__":
    asyncio.run(test_video_api())
