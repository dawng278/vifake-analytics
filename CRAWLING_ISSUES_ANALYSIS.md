# URL Crawling Issues Analysis

## 🔍 Current Status

### ✅ Working Platforms
- **YouTube**: oEmbed API + direct thumbnail URL
- **X/Twitter**: oEmbed API + og:image

### ❌ Problematic Platforms
- **TikTok**: oEmbed API blocked
- **Facebook**: Login wall + CDN restrictions

## 🚨 Root Causes

### 1. TikTok oEmbed Blocking
```bash
curl "https://www.tiktok.com/oembed?url=..." → HTTP 403/No response
```
**Issue**: TikTok加强了反爬虫保护，oEmbed API需要更sophisticated的headers和可能的rate limiting。

### 2. Facebook Login Wall
**Issue**: 
- HTML只能通过登录访问
- `og:image`被CDN限制
- Preview metadata有限

### 3. Anti-Bot Headers Insufficient
Current headers可能被platforms识别为bot。

## 🔧 Proposed Solutions

### Solution 1: Enhanced Headers + Rate Limiting
```python
_ENHANCED_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Ch-UA': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-UA-Mobile': '?0',
    'Sec-Ch-UA-Platform': '"Windows"',
}
```

### Solution 2: yt-dlp Fallback
```python
import yt_dlp

def extract_tiktok_metadata(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'simulate': True,  # Don't download
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title'),
            'description': info.get('description'),
            'thumbnail': info.get('thumbnail'),
            'uploader': info.get('uploader'),
        }
```

### Solution 3: Playwright with Cookies
```python
from playwright.async_api import async_playwright

async def extract_facebook_content(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        # Load saved cookies if available
        # context.add_cookies([...])
        
        page = await context.new_page()
        await page.goto(url)
        
        # Wait for content to load
        await page.wait_for_selector('[role="article"]', timeout=10000)
        
        content = await page.content()
        await browser.close()
        
        return extract_from_html(content)
```

### Solution 4: Multiple Fallback Strategy
```python
def extract_content_fallback(url, platform):
    extractors = [
        try_oembed_api,
        try_yt_dlp,
        try_playwright,
        try_basic_crawl,
    ]
    
    for extractor in extractors:
        try:
            result = extractor(url, platform)
            if result and len(result.get('text', '')) > 50:
                return result
        except Exception as e:
            logger.warning(f"Extractor {extractor.__name__} failed: {e}")
            continue
    
    return {'text': '', 'image_url': None}
```

## 📊 Success Rate Estimates

| Platform | Current Success | With Enhanced Headers | With yt-dlp | With Playwright |
|----------|----------------|-------------------|---------------|-----------------|
| TikTok | ~30% | ~60% | ~85% | ~95% |
| Facebook | ~40% | ~50% | ~70% | ~90% |
| YouTube | ~95% | ~95% | ~95% | ~95% |

## 🎯 Implementation Priority

1. **High Priority**: Enhanced headers + rate limiting
2. **Medium Priority**: yt-dlp integration
3. **Low Priority**: Playwright (requires more resources)

## 🧪 Testing Commands

```bash
# Test enhanced headers
curl -H @enhanced_headers.json "https://www.tiktok.com/oembed?url=..."

# Test yt-dlp
python3 -c "
import yt_dlp
info = yt_dlp.YoutubeDL({'quiet':True}).extract_info('TIKTOK_URL', download=False)
print('Title:', info.get('title'))
print('Thumbnail:', info.get('thumbnail'))
"

# Test current extraction
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Authorization: Bearer demo-token-123" \
  -H "Content-Type: application/json" \
  -d '{"url":"TIKTOK_URL","platform":"tiktok"}'
```

## 📝 Next Steps

1. Implement enhanced headers in `_CRAWL_HEADERS`
2. Add yt-dlp as fallback for TikTok
3. Test with real TikTok URLs
4. Monitor success rates and adjust
