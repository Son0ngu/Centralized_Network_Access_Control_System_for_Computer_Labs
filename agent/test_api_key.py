"""
Test API Key và Agent Registration
-----------------------------------
Kiểm tra xem API Key có hợp lệ và có quyền đăng ký agent không.
"""

import sys
import os
import json
import requests

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_config


def test_server_connection(server_url: str) -> bool:
    """Test kết nối đến server."""
    print(f"\n{'='*60}")
    print("TEST 1: Kiểm tra kết nối Server")
    print(f"{'='*60}")
    
    try:
        # Try health endpoint or root
        response = requests.get(f"{server_url}/", timeout=5)
        print(f"✅ Server đang chạy tại {server_url}")
        print(f"   Status: {response.status_code}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"❌ Không thể kết nối đến {server_url}")
        print("   → Kiểm tra server có đang chạy không")
        return False
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return False


def test_api_key_format(api_key: str) -> bool:
    """Kiểm tra format API Key."""
    print(f"\n{'='*60}")
    print("TEST 2: Kiểm tra format API Key")
    print(f"{'='*60}")
    
    if not api_key:
        print("❌ API Key trống hoặc không được cấu hình")
        print("   → Thêm api_key vào agent_config.json tại auth.api_key")
        return False
    
    print(f"   API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")
    
    if not api_key.startswith("fc_"):
        print("❌ API Key không có tiền tố 'fc_'")
        print("   → API Key phải bắt đầu bằng 'fc_'")
        return False
    
    if len(api_key) < 20:
        print("❌ API Key quá ngắn")
        return False
    
    print("✅ Format API Key hợp lệ")
    return True


def test_api_key_validation(server_url: str, api_key: str) -> bool:
    """Test validate API Key với server."""
    print(f"\n{'='*60}")
    print("TEST 3: Validate API Key với Server")
    print(f"{'='*60}")
    
    # Test với endpoint đăng ký (sẽ trả 400 nếu thiếu body nhưng API key hợp lệ)
    # Hoặc 401 nếu API key không hợp lệ
    
    headers = {
        'Content-Type': 'application/json',
        'X-API-KEY': api_key
    }
    
    try:
        # Gửi request với body rỗng để test API key
        response = requests.post(
            f"{server_url}/api/agents/register",
            json={},  # Empty body
            headers=headers,
            timeout=10
        )
        
        print(f"   Status Code: {response.status_code}")
        
        try:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        except:
            print(f"   Response: {response.text[:200]}")
        
        if response.status_code == 401:
            print("\n❌ API Key bị từ chối (401 Unauthorized)")
            print("   Nguyên nhân có thể:")
            print("   1. API Key không tồn tại trong database")
            print("   2. API Key đã bị thu hồi (revoked)")
            print("   3. API Key đã hết hạn")
            print("   4. API Key không có quyền 'agent_register' hoặc 'register'")
            print("\n   → Giải pháp: Tạo API Key mới từ Admin Dashboard")
            return False
            
        elif response.status_code == 400:
            print("\n✅ API Key hợp lệ! (Server trả 400 vì thiếu dữ liệu đăng ký)")
            return True
            
        elif response.status_code == 200 or response.status_code == 201:
            print("\n✅ API Key hợp lệ!")
            return True
            
        else:
            print(f"\n⚠️ Status code không mong đợi: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Không thể kết nối đến server")
        return False
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return False


def test_full_registration(server_url: str, api_key: str) -> bool:
    """Test đăng ký agent đầy đủ."""
    print(f"\n{'='*60}")
    print("TEST 4: Test đăng ký Agent đầy đủ")
    print(f"{'='*60}")
    
    import socket
    import platform
    
    # Build agent info
    agent_info = {
        "device_id": "test_device_001",
        "hostname": socket.gethostname(),
        "ip_address": "127.0.0.1",
        "os_type": platform.system(),
        "os_version": platform.version(),
        "agent_version": "2.2-Test"
    }
    
    headers = {
        'Content-Type': 'application/json',
        'X-API-KEY': api_key
    }
    
    print(f"   Agent Info: {json.dumps(agent_info, indent=2)}")
    
    try:
        response = requests.post(
            f"{server_url}/api/agents/register",
            json=agent_info,
            headers=headers,
            timeout=15
        )
        
        print(f"\n   Status Code: {response.status_code}")
        
        try:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        except:
            print(f"   Response: {response.text[:500]}")
        
        if response.status_code in [200, 201]:
            print("\n✅ Đăng ký agent thành công!")
            if 'agent_id' in str(data):
                print("   Agent đã được cấp ID từ server")
            return True
        elif response.status_code == 401:
            print("\n❌ Lỗi xác thực API Key")
            return False
        elif response.status_code == 409:
            print("\n⚠️ Agent đã tồn tại (có thể do device_id trùng)")
            return True
        else:
            print(f"\n❌ Đăng ký thất bại với status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return False


def show_config_info(config: dict):
    """Hiển thị thông tin cấu hình."""
    print(f"\n{'='*60}")
    print("THÔNG TIN CẤU HÌNH")
    print(f"{'='*60}")
    
    server_config = config.get('server', {})
    auth_config = config.get('auth', {})
    
    # Server URLs
    urls = server_config.get('urls', [])
    if not urls and server_config.get('url'):
        urls = [server_config.get('url')]
    
    print(f"Server URLs: {urls}")
    print(f"API Key configured: {'Yes' if auth_config.get('api_key') else 'No'}")
    
    if auth_config.get('api_key'):
        key = auth_config['api_key']
        print(f"API Key preview: {key[:15]}..." if len(key) > 15 else f"API Key: {key}")


def main():
    print("="*60)
    print("  TEST API KEY VÀ AGENT REGISTRATION")
    print("="*60)
    
    # Load config
    try:
        config = get_config()
    except Exception as e:
        print(f"❌ Không thể load config: {e}")
        return
    
    show_config_info(config)
    
    # Get server URL
    server_config = config.get('server', {})
    server_urls = server_config.get('urls', [])
    if not server_urls and server_config.get('url'):
        server_urls = [server_config.get('url')]
    
    if not server_urls:
        print("\n❌ Không có server URL trong config!")
        return
    
    server_url = server_urls[0]
    
    # Get API Key
    api_key = config.get('auth', {}).get('api_key', '')
    
    # Run tests
    results = []
    
    # Test 1: Server connection
    results.append(("Kết nối Server", test_server_connection(server_url)))
    
    if not results[-1][1]:
        print("\n⚠️ Dừng test do không kết nối được server")
        show_summary(results)
        return
    
    # Test 2: API Key format
    results.append(("Format API Key", test_api_key_format(api_key)))
    
    if not results[-1][1]:
        print("\n⚠️ Dừng test do API Key không hợp lệ")
        show_summary(results)
        return
    
    # Test 3: API Key validation
    results.append(("Validate API Key", test_api_key_validation(server_url, api_key)))
    
    if not results[-1][1]:
        show_summary(results)
        show_fix_instructions()
        return
    
    # Test 4: Full registration
    results.append(("Đăng ký Agent", test_full_registration(server_url, api_key)))
    
    show_summary(results)


def show_summary(results):
    """Hiển thị tóm tắt kết quả."""
    print(f"\n{'='*60}")
    print("TÓM TẮT KẾT QUẢ")
    print(f"{'='*60}")
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {name}")
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    print(f"\nKết quả: {passed}/{total} tests passed")


def show_fix_instructions():
    """Hiển thị hướng dẫn sửa lỗi."""
    print(f"\n{'='*60}")
    print("HƯỚNG DẪN SỬA LỖI")
    print(f"{'='*60}")
    print("""
1. Đăng nhập Admin Dashboard (http://localhost:5000/admin)

2. Vào mục "API Keys" → "Create New API Key"

3. Tạo API Key với:
   - Name: "Agent Registration Key"
   - Permissions: chọn "agent_register" hoặc "register"
   - Expiration: tuỳ chọn (để trống = không hết hạn)

4. Copy API Key được tạo (bắt đầu bằng fc_...)

5. Cập nhật file agent/agent_config.json:
   {
     "auth": {
       "api_key": "fc_xxxxxxxxxxxxxxxxxxxxxxxx"
     }
   }

6. Chạy lại test này để kiểm tra
""")


if __name__ == "__main__":
    main()
