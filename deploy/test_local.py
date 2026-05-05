
import subprocess
import time
import requests
import json
from datetime import datetime

def test_api_gateway():
    print('🌐 Testing API Gateway...')
    
    # Start API Gateway
    api_process = subprocess.Popen([
        sys.executable, 'main.py'
    ], cwd='backend_services/api_gateway', 
       stdout=subprocess.PIPE, 
       stderr=subprocess.PIPE)
    
    # Wait for startup
    time.sleep(5)
    
    try:
        # Test health endpoint
        response = requests.get('http://localhost:8000/api/v1/health', timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            print(f'✅ API Health: {health_data.get("status")}')
            return True, api_process, health_data
        else:
            print(f'❌ API Health failed: {response.status_code}')
            return False, api_process, None
    except Exception as e:
        print(f'❌ API connection failed: {e}')
        return False, api_process, None

def test_analysis_endpoint(api_process):
    print('🧪 Testing Analysis Endpoint...')
    
    try:
        headers = {'Authorization': 'Bearer $AUTH_TOKEN'}
        payload = {
            'url': 'https://example.com/test-safe',
            'platform': 'youtube',
            'priority': 'normal'
        }
        
        response = requests.post(
            'http://localhost:8000/api/v1/analyze',
            json=payload,
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            job_id = result.get('job_id')
            print(f'✅ Analysis Job Created: {job_id}')
            
            # Test job status
            time.sleep(2)
            status_response = requests.get(
                f'http://localhost:8000/api/v1/job/{job_id}',
                headers=headers,
                timeout=10
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f'✅ Job Status: {status_data.get("status")}')
                return True
            else:
                print(f'❌ Job status failed: {status_response.status_code}')
                return False
        else:
            print(f'❌ Analysis endpoint failed: {response.status_code}')
            return False
            
    except Exception as e:
        print(f'❌ Analysis test failed: {e}')
        return False

def main():
    print('🚀 ViFake Analytics Local Test Suite')
    print('=' * 50)
    
    # Test API Gateway
    success, api_process, health_data = test_api_gateway()
    
    if success:
        # Test analysis endpoint
        analysis_success = test_analysis_endpoint(api_process)
        
        # Get final stats
        try:
            stats_response = requests.get('http://localhost:8000/api/v1/stats', timeout=10)
            if stats_response.status_code == 200:
                stats_data = stats_response.json()
                print(f'📊 Final Stats: {stats_data.get("active_jobs", 0)} active jobs')
        except:
            pass
        
        print('\n🎉 Local Deployment Test Completed!')
        print('✅ API Gateway is running successfully')
        print('📖 Documentation: http://localhost:8000/docs')
        print('🏥 Health Check: http://localhost:8000/api/v1/health')
        
        # Keep running for manual testing
        print('\n🔄 API Gateway is running for manual testing...')
        print('💡 Press Ctrl+C to stop')
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print('\n🛑 Stopping API Gateway...')
            api_process.terminate()
            api_process.wait()
            print('✅ Test completed')
    else:
        print('❌ API Gateway failed to start')
        if api_process:
            api_process.terminate()
            api_process.wait()

if __name__ == '__main__':
    main()
