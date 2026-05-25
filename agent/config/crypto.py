"""
Encrypt/decrypt agent_config.json using Fernet (AES-128-CBC).
Key is derived from machine identity (hostname + MAC address) so the
config file is only readable on the same machine.
"""

import base64
import hashlib
import json
import logging
import socket
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("config.crypto")

# Encrypted config uses .enc extension
ENCRYPTED_EXT = ".enc"


def _get_machine_key() -> bytes:
    """Derive a Fernet key from machine identity (hostname + MAC)."""
    hostname = socket.gethostname()
    mac = hex(uuid.getnode())
    seed = f"SAINT:{hostname}:{mac}".encode()
    # SHA-256 → take first 32 bytes → base64-encode for Fernet (requires url-safe b64)
    digest = hashlib.sha256(seed).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_config(config: Dict[str, Any], path: Path) -> bool:
    """Encrypt config dict and write to file."""
    try:
        key = _get_machine_key()
        fernet = Fernet(key)

        plaintext = json.dumps(config, indent=4, ensure_ascii=False).encode("utf-8")
        encrypted = fernet.encrypt(plaintext)

        enc_path = path.with_suffix(path.suffix + ENCRYPTED_EXT)
        enc_path.parent.mkdir(parents=True, exist_ok=True)
        enc_path.write_bytes(encrypted)

        # Remove plaintext file if it exists
        if path.exists():
            path.unlink()

        logger.info(f"Config encrypted and saved to {enc_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to encrypt config: {e}")
        return False


def decrypt_config(path: Path) -> Optional[Dict[str, Any]]:
    """Read and decrypt config from encrypted file."""
    enc_path = path.with_suffix(path.suffix + ENCRYPTED_EXT)
    if not enc_path.exists():
        return None

    try:
        key = _get_machine_key()
        fernet = Fernet(key)

        encrypted = enc_path.read_bytes()
        plaintext = fernet.decrypt(encrypted)

        return json.loads(plaintext.decode("utf-8"))
    except InvalidToken:
        logger.error(f"Cannot decrypt {enc_path} — wrong machine or corrupted file")
        return None
    except Exception as e:
        logger.error(f"Failed to decrypt config: {e}")
        return None


def migrate_plaintext_to_encrypted(path: Path) -> bool:
    """If plaintext config exists but encrypted does not, encrypt it."""
    enc_path = path.with_suffix(path.suffix + ENCRYPTED_EXT)
    if path.exists() and not enc_path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
            if encrypt_config(config, path):
                logger.info(f"Migrated plaintext config to encrypted: {enc_path}")
                return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
    return False
