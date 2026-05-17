# AI Video Test URLs for ViFake Analytics

## Sources for AI-Generated Videos

### 1. **AI Avatar Platforms**
- **Synthesia**: `https://www.synthesia.io/` (exported TikTok videos)
- **HeyGen**: `https://www.heygen.com/` (AI avatar videos)
- **D-ID**: `https://www.d-id.com/` (talking head videos)

### 2. **Deepfake Examples**
- **DeepFaceLab**: `https://github.com/iperov/DeepFaceLive` (test videos)
- **Faceswap**: `https://github.com/matthewdee1/ffhq-dataset` (sample videos)

### 3. **AI Animation Tools**
- **RunwayML**: `https://runwayml.com/` (AI-generated video clips)
- **Kaiber**: `https://kaiber.ai/` (AI music videos)
- **Pika Labs**: `https://pika.art/` (AI animation)

### 4. **Text-to-Video**
- **Sora**: OpenAI videos (when available)
- **Pika**: Text-to-video generation
- **Gen-2**: RunwayML text-to-video

## Test Categories

### **Definitely AI-Generated** (Should detect as AI)
- 3D animated characters
- AI talking heads with unnatural lip sync
- AI-generated backgrounds/landscapes
- Synthetic voice + AI avatar combinations

### **Definitely Real** (Should NOT detect as AI)
- Real human recordings
- Authentic user-generated content
- Professional but real videos
- Live streams/recordings

### **Edge Cases** (May need threshold tuning)
- Heavy edited videos with filters
- Motion graphics with real footage
- Deepfake with high quality
- AI-assisted editing

## Testing Strategy

### 1. **Start with Clear Cases**
```python
# High confidence AI examples
ai_videos = [
    "https://v16-web.tiktokcdn.com/share/video/[ai_avatar_1].mp4",
    "https://v16-web.tiktokcdn.com/share/video/[ai_avatar_2].mp4",
]

# High confidence real examples  
real_videos = [
    "https://v16-web.tiktokcdn.com/share/video/[real_human_1].mp4",
    "https://v16-web.tiktokcdn.com/share/video/[real_human_2].mp4",
]
```

### 2. **Measure Detection Accuracy**
- True Positive Rate (AI detected as AI)
- False Positive Rate (Real detected as AI)
- Confidence scores distribution
- Processing time per video

### 3. **Threshold Optimization**
```python
# Current threshold: >0.7 confidence = AI
# Test ranges: 0.5, 0.6, 0.7, 0.8, 0.9
# Choose threshold with best F1 score
```

## Manual Testing Checklist

### **For Each Test Video:**
- [ ] Video URL accessible
- [ ] Audio extraction works
- [ ] Frame extraction works (8 frames)
- [ ] Whisper transcription produces text
- [ ] CLIP analysis returns confidence scores
- [ ] Fusion logic produces final verdict
- [ ] Result matches expectation (AI/Real)

### **Performance Metrics:**
- [ ] Processing time < 30 seconds
- [ ] Memory usage < 400MB
- [ ] Temporary files cleaned up
- [ ] No errors in logs

## Sample Test Results Format

```json
{
  "video_url": "https://...",
  "expected_ai": true,
  "result": {
    "verdict": "SUSPICIOUS",
    "confidence": 0.85,
    "is_ai_generated": true,
    "ai_confidence": 0.78,
    "processing_ms": 15420
  },
  "correct": true,
  "notes": "AI avatar clearly detected, confidence high"
}
```

## Next Steps

1. **Collect 10-20 test videos** (mix of AI and real)
2. **Run automated tests** using `tests/manual/test_video_ai.py`
3. **Analyze results** and adjust thresholds if needed
4. **Document edge cases** for future improvements
