"""
该模块通过验证安装时生成的密钥与当前设备的硬件信息
是否匹配，防止程序被未授权地用于其他设备。
"""
import winreg
import base64
import ctypes
from ctypes import wintypes
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from .config import Config
from .info import INFO

class CheckAuthorization:
    """用于校验安装时生成的密钥，防止程序被用于其他设备"""
    def aes_decrypt(self, ciphertext):
        """使用AES-CBC模式解密数据"""
        try:
            # 解码Base64
            decoded_ciphertext = base64.b64decode(ciphertext)
            # 创建AES解密器
            cipher = AES.new(Config.AES_KEY, AES.MODE_CBC, Config.AES_IV)
            # 解密并去除填充
            plaintext = unpad(cipher.decrypt(decoded_ciphertext), AES.block_size)
            return plaintext.decode('utf-8').rstrip('\x00')  # 移除可能的空字符填充
        except (ValueError, TypeError, base64.binascii.Error) as e:
            print(INFO.get("auth_decrypt_failed").format(error=str(e)))
            return None

    def get_disk_serial(self, kernel32=None) -> str:
        """获取C盘的序列号"""
        if kernel32 is None:
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

        # 常量定义
        generic_read = 0x80000000
        file_share_read = 0x00000001
        file_share_write = 0x00000002
        open_existing = 3

        # 打开卷设备
        h_volume = kernel32.CreateFileW(
            r'\\.\\C:',
            generic_read,
            file_share_read | file_share_write,
            None,
            open_existing,
            0,
            None
        )

        if h_volume == wintypes.HANDLE(-1).value:
            return ""

        try:
            volume_serial = wintypes.DWORD()
            # 获取卷信息
            success = kernel32.GetVolumeInformationW(
                r'C:\\',
                None, 0,
                ctypes.byref(volume_serial),
                None, None,
                None, 0
            )
            if success:
                return str(volume_serial.value)
            return ""
        finally:
            kernel32.CloseHandle(h_volume)

    def check_authorization(self):
        """验证程序是否在授权设备上运行"""
        reg_path = r"Software\\MyProtectedApp"

        try:
            # 读取注册表中的加密数据
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_READ)
            encrypted_data, _ = winreg.QueryValueEx(key, "AuthData")
            winreg.CloseKey(key)

            # 解密数据（调用实例方法）
            decrypted_data = self.aes_decrypt(encrypted_data)
            if not decrypted_data:
                return False

            # 解密后的数据格式: "硬盘序列号|安装ID"
            parts = decrypted_data.split('|')
            if len(parts) != 2:
                return False

            saved_disk_serial, _ = parts  # 移除未使用的变量
            current_disk_serial = self.get_disk_serial()  # 调用实例方法

            # 验证硬盘序列号是否匹配
            return saved_disk_serial == current_disk_serial

        except FileNotFoundError:
            print(INFO.get("auth_not_found"))
            return False
        except PermissionError:
            print(INFO.get("auth_permission_denied"))
            return False
        except (ValueError, TypeError) as e:  # 更具体的异常捕获
            print(INFO.get("auth_verify_failed").format(error=str(e)))
            return False
