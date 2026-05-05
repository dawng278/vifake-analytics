#!/usr/bin/env python3
"""
ViFake Analytics Web Interface Test Script
Test the web interface with API Gateway
"""

import requests
import time
import json
import subprocess
import sys
from pathlib import Path

class WebInterfaceTester:
    """Test the web interface functionality"""
    
    def __init__(self):
        self.api_base = "http://localhost:8000"
        self.auth_token = "demo-token-123"
        self.web_port = 8080
        
    def test_api_gateway(self):
        """Test if API Gateway is running"""
        print("🔍 Testing API Gateway...")
        
        try:
            response = requests.get(f"{self.api_base}/api/v1/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                print("✅ API Gateway is running!")
                print(f"   Status: {health.get('status')}")
                print(f"   Version: {health.get('version')}")
                return True
            else:
                print(f"❌ API Gateway responded with: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print("❌ API Gateway is not running")
            print("💡 Start it with: cd backend_services/api_gateway && python3 main.py")
            return False
        except Exception as e:
            print(f"❌ API Gateway test failed: {e}")
            return False
    
    def test_analysis_flow(self):
        """Test complete analysis flow"""
        print("\n🧪 Testing Analysis Flow...")
        
        try:
            # Test 1: Safe content
            print("\n📝 Test 1: Safe content analysis")
            result1 = self.analyze_content(
                "https://youtube.com/watch?v=safe123",
                "youtube",
                "normal"
            )
            
            if result1:
                print("✅ Safe content test passed")
                print(f"   Job ID: {result1.get('job_id')}")
                print(f"   Status: {result1.get('status')}")
            
            # Test 2: Scam content
            print("\n🚨 Test 2: Scam content analysis")
            result2 = self.analyze_content(
                "https://youtube.com/watch?v=scam456",
                "youtube", 
                "high"
            )
            
            if result2:
                print("✅ Scam content test passed")
                print(f"   Job ID: {result2.get('job_id')}")
                print(f"   Status: {result2.get('status')}")
            
            # Test 3: TikTok content
            print("\n🎵 Test 3: TikTok content analysis")
            result3 = self.analyze_content(
                "https://tiktok.com/@user/test789",
                "tiktok",
                "normal"
            )
            
            if result3:
                print("✅ TikTok content test passed")
                print(f"   Job ID: {result3.get('job_id')}")
                print(f"   Status: {result3.get('status')}")
            
            return True
            
        except Exception as e:
            print(f"❌ Analysis flow test failed: {e}")
            return False
    
    def analyze_content(self, url, platform, priority):
        """Analyze content and return result"""
        try:
            # Submit analysis
            response = requests.post(
                f"{self.api_base}/api/v1/analyze",
                json={
                    "url": url,
                    "platform": platform,
                    "priority": priority
                },
                headers={
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json"
                },
                timeout=15
            )
            
            if response.status_code != 200:
                print(f"❌ Analysis submission failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
            
            result = response.json()
            job_id = result.get('job_id')
            
            if not job_id:
                print("❌ No job ID returned")
                return None
            
            # Wait for completion
            print(f"⏳ Waiting for job {job_id} to complete...")
            
            for i in range(30):  # Wait up to 30 seconds
                time.sleep(1)
                
                status_response = requests.get(
                    f"{self.api_base}/api/v1/job/{job_id}",
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                    timeout=10
                )
                
                if status_response.status_code == 200:
                    job_data = status_response.json()
                    
                    if job_data.get('status') == 'completed':
                        print(f"✅ Job {job_id} completed!")
                        return job_data
                    elif job_data.get('status') == 'failed':
                        print(f"❌ Job {job_id} failed: {job_data.get('error')}")
                        return job_data
                    else:
                        progress = job_data.get('progress', 0)
                        stage = job_data.get('current_stage', 'Unknown')
                        print(f"   Progress: {progress:.1f}% - {stage}")
                else:
                    print(f"⚠️ Status check failed: {status_response.status_code}")
            
            print(f"⏰ Job {job_id} timed out")
            return None
            
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            return None
    
    def test_web_interface_files(self):
        """Test if web interface files exist"""
        print("\n📁 Testing Web Interface Files...")
        
        web_dir = Path(__file__).parent
        required_files = [
            "index.html",
            "README.md",
            "start_server.py"
        ]
        
        all_exist = True
        for file_name in required_files:
            file_path = web_dir / file_name
            if file_path.exists():
                print(f"✅ {file_name} exists")
            else:
                print(f"❌ {file_name} missing")
                all_exist = False
        
        return all_exist
    
    def start_web_server(self):
        """Start the web interface server"""
        print(f"\n🚀 Starting Web Interface Server...")
        
        try:
            # Start server in background
            process = subprocess.Popen([
                sys.executable, "start_server.py", str(self.web_port)
            ], cwd=Path(__file__).parent)
            
            print(f"⏳ Waiting for server to start...")
            time.sleep(2)
            
            # Test if server is running
            try:
                response = requests.get(f"http://localhost:{self.web_port}", timeout=5)
                if response.status_code == 200:
                    print(f"✅ Web server running on http://localhost:{self.web_port}")
                    return True
                else:
                    print(f"❌ Web server responded with: {response.status_code}")
                    return False
            except:
                print(f"⚠️ Web server may still be starting...")
                print(f"💡 Try opening http://localhost:{self.web_port} manually")
                return True
                
        except Exception as e:
            print(f"❌ Failed to start web server: {e}")
            return False
    
    def run_complete_test(self):
        """Run complete test suite"""
        print("🧪 ViFake Analytics Web Interface Test Suite")
        print("=" * 50)
        
        # Test 1: API Gateway
        api_ok = self.test_api_gateway()
        
        if not api_ok:
            print("\n❌ API Gateway is required for testing")
            print("💡 Please start API Gateway first:")
            print("   cd backend_services/api_gateway")
            print("   python3 main.py")
            return False
        
        # Test 2: Web interface files
        files_ok = self.test_web_interface_files()
        
        if not files_ok:
            print("\n❌ Web interface files are missing")
            return False
        
        # Test 3: Analysis flow
        analysis_ok = self.test_analysis_flow()
        
        # Test 4: Web server
        web_ok = self.start_web_server()
        
        # Summary
        print("\n📊 Test Results Summary:")
        print(f"   API Gateway: {'✅ PASS' if api_ok else '❌ FAIL'}")
        print(f"   Web Files: {'✅ PASS' if files_ok else '❌ FAIL'}")
        print(f"   Analysis Flow: {'✅ PASS' if analysis_ok else '❌ FAIL'}")
        print(f"   Web Server: {'✅ PASS' if web_ok else '❌ FAIL'}")
        
        overall = api_ok and files_ok and analysis_ok and web_ok
        
        if overall:
            print("\n🎉 ALL TESTS PASSED!")
            print(f"🌐 Web Interface: http://localhost:{self.web_port}")
            print(f"📖 API Documentation: http://localhost:8000/docs")
            print("\n✅ Ready for extension development!")
        else:
            print("\n⚠️ Some tests failed. Check the errors above.")
        
        return overall

def main():
    """Main function"""
    tester = WebInterfaceTester()
    success = tester.run_complete_test()
    
    if success:
        print("\n🚀 Next steps:")
        print("1. Open http://localhost:8080 in browser")
        print("2. Test the web interface")
        print("3. Try different URLs and platforms")
        print("4. Monitor real-time progress")
        print("5. Check detailed results")
        print("\n💡 When ready, start extension development!")
    
    return success

if __name__ == "__main__":
    main()
