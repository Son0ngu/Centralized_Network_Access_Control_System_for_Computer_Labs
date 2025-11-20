import winreg

def get_windows_settings_id():
    try:
        # Vị trí chứa ID hiển thị trong Settings > About
        # Lưu ý: Microsoft có thể đổi vị trí này tùy version Windows
        path = r"SOFTWARE\Microsoft\SQMClient"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        value, type = winreg.QueryValueEx(key, "MachineId")
        
        # Bỏ dấu ngoặc nhọn {} nếu có
        return value.strip("{}")
    except Exception as e:
        return f"Không tìm thấy: {e}"

print(f"Windows ID (Settings): {get_windows_settings_id()}")