"""Security utilities for the Intelligent PR Assistant MVP."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from config.config import config

logger = logging.getLogger(__name__)


class SecurityManager:
    """Security manager for authentication, encryption, and token management."""
    
    def __init__(self):
        """Initialize security manager with configuration."""
        self.jwt_secret = config.security.jwt_secret
        self.jwt_algorithm = config.security.jwt_algorithm
        self.jwt_expires_in = config.security.jwt_expires_in
        
        # Initialize encryption
        self._encryption_key = None
        self._fernet = None
        self._init_encryption()
    
    def _init_encryption(self):
        """Initialize encryption components."""
        try:
            # Generate or derive encryption key
            if hasattr(config.security, 'encryption_key') and config.security.encryption_key:
                # Use provided key
                key = config.security.encryption_key.encode()
            else:
                # Derive key from JWT secret
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'pr_assistant_salt',  # In production, use random salt
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(self.jwt_secret.encode()))
            
            self._encryption_key = key
            self._fernet = Fernet(key)
            
            logger.info("Encryption initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {str(e)}")
            raise
    
    def generate_jwt_token(self, payload: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Generate JWT token with payload.
        
        Args:
            payload: Token payload data
            expires_delta: Custom expiration time
            
        Returns:
            JWT token string
        """
        try:
            # Set expiration
            if expires_delta:
                expire = datetime.utcnow() + expires_delta
            else:
                # Parse expires_in string (e.g., "24h", "30m", "7d")
                expire = self._parse_expires_in(self.jwt_expires_in)
            
            # Add standard claims
            token_payload = {
                **payload,
                'exp': expire,
                'iat': datetime.utcnow(),
                'iss': config.name
            }
            
            # Generate token
            token = jwt.encode(token_payload, self.jwt_secret, algorithm=self.jwt_algorithm)
            
            logger.debug(f"Generated JWT token for subject: {payload.get('sub', 'unknown')}")
            
            return token
            
        except Exception as e:
            logger.error(f"Failed to generate JWT token: {str(e)}")
            raise
    
    def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm],
                issuer=config.name
            )
            
            logger.debug(f"Verified JWT token for subject: {payload.get('sub', 'unknown')}")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            raise jwt.InvalidTokenError("Token has expired")
        except jwt.InvalidIssuerError:
            logger.warning("JWT token has invalid issuer")
            raise jwt.InvalidTokenError("Invalid token issuer")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to verify JWT token: {str(e)}")
            raise jwt.InvalidTokenError("Token verification failed")
    
    def encrypt_data(self, data: str) -> str:
        """
        Encrypt sensitive data.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Encrypted data as base64 string
        """
        try:
            if not self._fernet:
                raise ValueError("Encryption not initialized")
            
            encrypted_data = self._fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error(f"Failed to encrypt data: {str(e)}")
            raise
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """
        Decrypt sensitive data.
        
        Args:
            encrypted_data: Encrypted data as base64 string
            
        Returns:
            Decrypted data string
        """
        try:
            if not self._fernet:
                raise ValueError("Encryption not initialized")
            
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self._fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode()
            
        except Exception as e:
            logger.error(f"Failed to decrypt data: {str(e)}")
            raise
    
    def hash_password(self, password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """
        Hash password with salt.
        
        Args:
            password: Password to hash
            salt: Optional salt (generated if not provided)
            
        Returns:
            Tuple of (hashed_password, salt)
        """
        try:
            if not salt:
                salt = secrets.token_hex(32)
            
            # Use PBKDF2 for password hashing
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt.encode(),
                iterations=100000,
            )
            
            hashed = base64.urlsafe_b64encode(kdf.derive(password.encode())).decode()
            
            return hashed, salt
            
        except Exception as e:
            logger.error(f"Failed to hash password: {str(e)}")
            raise
    
    def verify_password(self, password: str, hashed_password: str, salt: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            password: Password to verify
            hashed_password: Stored password hash
            salt: Password salt
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            # Hash the provided password with the same salt
            test_hash, _ = self.hash_password(password, salt)
            
            # Compare hashes using constant-time comparison
            return hmac.compare_digest(hashed_password, test_hash)
            
        except Exception as e:
            logger.error(f"Failed to verify password: {str(e)}")
            return False
    
    def generate_api_key(self, prefix: str = "pa") -> str:
        """
        Generate secure API key.
        
        Args:
            prefix: Key prefix
            
        Returns:
            Generated API key
        """
        try:
            # Generate random key
            key_bytes = secrets.token_bytes(32)
            key_b64 = base64.urlsafe_b64encode(key_bytes).decode().rstrip('=')
            
            return f"{prefix}_{key_b64}"
            
        except Exception as e:
            logger.error(f"Failed to generate API key: {str(e)}")
            raise
    
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """
        Verify webhook signature.
        
        Args:
            payload: Raw webhook payload
            signature: Signature from webhook headers
            secret: Webhook secret
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Generate expected signature
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Remove algorithm prefix if present (e.g., "sha256=")
            if '=' in signature:
                signature = signature.split('=', 1)[1]
            
            # Compare signatures using constant-time comparison
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Failed to verify webhook signature: {str(e)}")
            return False
    
    def sanitize_input(self, data: str, max_length: int = 1000) -> str:
        """
        Sanitize user input.
        
        Args:
            data: Input data to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized data
        """
        if not isinstance(data, str):
            data = str(data)
        
        # Truncate if too long
        if len(data) > max_length:
            data = data[:max_length]
        
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&', '\x00', '\r', '\n']
        for char in dangerous_chars:
            data = data.replace(char, '')
        
        return data.strip()
    
    def _parse_expires_in(self, expires_in: str) -> datetime:
        """
        Parse expires_in string to datetime.
        
        Args:
            expires_in: Expiration string (e.g., "24h", "30m", "7d")
            
        Returns:
            Expiration datetime
        """
        try:
            if expires_in.endswith('h'):
                hours = int(expires_in[:-1])
                return datetime.utcnow() + timedelta(hours=hours)
            elif expires_in.endswith('m'):
                minutes = int(expires_in[:-1])
                return datetime.utcnow() + timedelta(minutes=minutes)
            elif expires_in.endswith('d'):
                days = int(expires_in[:-1])
                return datetime.utcnow() + timedelta(days=days)
            elif expires_in.endswith('s'):
                seconds = int(expires_in[:-1])
                return datetime.utcnow() + timedelta(seconds=seconds)
            else:
                # Default to 24 hours
                return datetime.utcnow() + timedelta(hours=24)
                
        except (ValueError, IndexError):
            logger.warning(f"Invalid expires_in format: {expires_in}, using default 24h")
            return datetime.utcnow() + timedelta(hours=24)


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 3600):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests = {}  # {client_id: [(timestamp, count), ...]}
    
    def is_allowed(self, client_id: str) -> bool:
        """
        Check if request is allowed for client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            True if request is allowed, False otherwise
        """
        now = datetime.utcnow().timestamp()
        window_start = now - self.window_seconds
        
        # Clean old entries
        if client_id in self._requests:
            self._requests[client_id] = [
                (ts, count) for ts, count in self._requests[client_id]
                if ts > window_start
            ]
        else:
            self._requests[client_id] = []
        
        # Count requests in current window
        total_requests = sum(count for _, count in self._requests[client_id])
        
        if total_requests >= self.max_requests:
            return False
        
        # Add current request
        self._requests[client_id].append((now, 1))
        return True
    
    def get_remaining_requests(self, client_id: str) -> int:
        """
        Get remaining requests for client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Number of remaining requests
        """
        now = datetime.utcnow().timestamp()
        window_start = now - self.window_seconds
        
        if client_id not in self._requests:
            return self.max_requests
        
        # Count requests in current window
        current_requests = sum(
            count for ts, count in self._requests[client_id]
            if ts > window_start
        )
        
        return max(0, self.max_requests - current_requests)


# Factory function for easy instantiation
def create_security_manager() -> SecurityManager:
    """Create and return a new security manager instance."""
    return SecurityManager()


def create_rate_limiter(max_requests: int = 100, window_seconds: int = 3600) -> RateLimiter:
    """Create and return a new rate limiter instance."""
    return RateLimiter(max_requests, window_seconds)
