import os
import hashlib
from unittest.mock import patch

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding


#
# 生成 RSA 私钥（PKCS#1 格式）
# openssl genrsa -out private_key.pem 2048
#
# 从私钥提取公钥（PEM 格式）
# openssl rsa -in private_key.pem -pubout -out public_key.pem
#
# 可选：将私钥转换为 PKCS#8 格式（兼容 Java）
# openssl pkcs8 -topk8 -inform PEM -in private_key.pem -outform PEM -nocrypt -out private_pkcs8.pem
#
# 对文件生成 SHA256 哈希并用私钥签名
# openssl dgst -sha256 -sign private_key.pem -out signature.bin file.txt
#
# 验证签名（需公钥）
# openssl dgst -sha256 -verify public_key.pem -signature signature.bin file.txt
#


def gen_key_pair(
        private_key_file_name: str = "private_key.pem",
        public_key_file_name: str = "public_key.pem"):
    # 生成私钥
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    # 保存私钥到 PEM 文件
    with open(private_key_file_name, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # 提取公钥并保存
    public_key = private_key.public_key()
    with open(public_key_file_name, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))

    return private_key, public_key


def sign_file(file_path: str, private_key_path: str, signature_path: str):
    # 读取文件内容
    with open(file_path, "rb") as f:
        data = f.read()

    # 加载私钥
    with open(private_key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None
        )

    # 生成签名（使用 PSS 填充）
    signature = private_key.sign(
        data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )

    # 保存签名
    with open(signature_path, "wb") as f:
        f.write(signature)


def verify_signature(file_path: str, public_key_path: str, signature_path: str) -> bool:
    # 读取文件、公钥和签名
    with open(file_path, "rb") as f:
        data = f.read()
    with open(public_key_path, "rb") as f:
        public_key = serialization.load_pem_public_key(f.read())
    with open(signature_path, "rb") as f:
        signature = f.read()

    # 验证签名
    try:
        public_key.verify(
            signature,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False


class SecurityValidator:
    @staticmethod
    def verify_hash(file_path, expected_hash):
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest() == expected_hash

    @staticmethod
    def verify_signature(file_path, public_key, signature_path):
        with open(file_path, "rb") as f:
            data = f.read()
        with open(signature_path, "rb") as f:
            signature = f.read()
        try:
            public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            return False
        except Exception as e:
            print(f"签名验证异常: {e}")
            return False

    @staticmethod
    def load_public_key(pem_path: str):
        with open(pem_path, "rb") as f:
            pem_data = f.read()
        public_key = serialization.load_pem_public_key(
            pem_data,
            backend=default_backend()
        )
        return public_key

class SecurityConfig:
    def __init__(self, enable_hash=True, enable_signature=False,
                 public_key_path=None, whitelist_hashes=None):
        self.enable_hash = enable_hash
        self.enable_signature = enable_signature
        self.public_key = SecurityValidator.load_public_key(public_key_path) if public_key_path else None
        self.whitelist = whitelist_hashes or {}


# ================= 测试准备 =================
def create_test_file(content: str = "test data") -> str:
    """创建临时测试文件"""
    test_path = "dummy.txt"
    with open(test_path, "w") as f:
        f.write(content)
    return test_path


def cleanup_files(*paths):
    """清理临时文件"""
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


# ================= 密钥生成测试 =================
def test_key_generation():
    """测试密钥对生成功能"""
    # 生成测试密钥对
    priv_key, pub_key = gen_key_pair("test_priv.pem", "test_pub.pem")

    # 验证文件存在性
    assert os.path.exists("test_priv.pem"), "私钥文件未生成"
    assert os.path.exists("test_pub.pem"), "公钥文件未生成"

    # 验证密钥有效性
    assert priv_key.key_size == 2048, "密钥长度不符合要求"
    assert pub_key.public_numbers().e == 65537, "公钥指数错误"

    # 清理临时文件
    cleanup_files("test_priv.pem", "test_pub.pem")


# ================= 签名验证测试 =================
def test_signature_workflow():
    """完整签名流程测试"""
    # 准备测试文件
    test_file = create_test_file()
    gen_key_pair("test_priv.pem", "test_pub.pem")

    # 生成签名
    sign_file(test_file, "test_priv.pem", "test.sig")
    assert os.path.exists("test.sig"), "签名文件未生成"

    # 正常验证测试
    assert verify_signature(test_file, "test_pub.pem", "test.sig"), "合法签名验证失败"

    # 篡改文件测试
    with open(test_file, "a") as f:
        f.write("tampered")
    assert not verify_signature(test_file, "test_pub.pem", "test.sig"), "篡改文件未检测到"

    # 清理
    cleanup_files(test_file, "test_priv.pem", "test_pub.pem", "test.sig")


# ================= 哈希验证测试 =================
def test_hash_validation():
    """文件哈希验证测试"""
    # 准备测试文件
    test_file = create_test_file("hash test")
    expected_hash = hashlib.sha256(b"hash test").hexdigest()

    # 正确哈希验证
    assert SecurityValidator.verify_hash(test_file, expected_hash), "正确哈希验证失败"

    # 错误哈希检测
    assert not SecurityValidator.verify_hash(test_file, "invalid_hash"), "错误哈希未检测到"

    cleanup_files(test_file)


# ================= 异常处理测试 =================
def test_exception_handling():
    """异常场景测试"""
    # 生成临时密钥对
    gen_key_pair("test_priv.pem", "test_pub.pem")

    # 无效公钥路径测试
    try:
        SecurityValidator.load_public_key("non_exist.pem")
        assert False, "不存在的公钥文件未触发异常"
    except Exception as e:
        assert isinstance(e, FileNotFoundError), f"错误的异常类型: {type(e)}"

    # 空文件签名测试
    empty_file = create_test_file("")
    sign_file(empty_file, "test_priv.pem", "empty.sig")
    assert verify_signature(empty_file, "test_pub.pem", "empty.sig")

    # 清理文件
    cleanup_files("test_priv.pem", "test_pub.pem", "empty.sig", empty_file)


# ================= 配置类测试 =================
def test_security_config():
    """安全配置类测试"""
    # Mock公钥加载
    with patch.object(SecurityValidator, 'load_public_key') as mock_load:
        mock_load.return_value = "MOCK_KEY"
        config = SecurityConfig(
            enable_signature=True,
            public_key_path="any.pem",
            whitelist_hashes={"dummy.txt": "abc123"}
        )
        assert config.public_key == "MOCK_KEY"
        mock_load.assert_called_once_with("any.pem")


# ================= 主测试入口 =================
if __name__ == "__main__":
    # 执行所有测试
    tests = [
        test_key_generation,
        test_signature_workflow,
        test_hash_validation,
        test_exception_handling,
        test_security_config
    ]

    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
        except AssertionError as e:
            print(f"[FAIL] {test.__name__} - {str(e)}")

    # 最终清理
    cleanup_files("test_priv.pem", "test_pub.pem", "test.sig")
