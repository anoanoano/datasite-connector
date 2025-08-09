"""
Access Control System - Authentication and authorization for content access.
"""

import asyncio
import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Set
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from passlib.context import CryptContext
from jose import JWTError, jwt

from .config import Config

logger = logging.getLogger(__name__)

@dataclass
class AccessToken:
    """Access token for content access."""
    token_id: str
    user_email: str
    permissions: List[str]
    datasets: List[str]  # Datasets this token can access
    created_at: datetime
    expires_at: datetime
    usage_count: int = 0
    last_used: Optional[datetime] = None

@dataclass
class AccessPolicy:
    """Access policy for a dataset."""
    dataset_name: str
    owner_email: str
    allowed_users: List[str]
    required_permissions: List[str]
    max_access_count: Optional[int] = None
    access_window: Optional[timedelta] = None
    created_at: datetime = None

@dataclass
class AccessAuditLog:
    """Audit log entry for access attempts."""
    timestamp: datetime
    user_email: str
    dataset_name: str
    action: str  # 'granted', 'denied', 'token_created', etc.
    token_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict] = None

class AccessControlSystem:
    """Manages authentication, authorization, and access control."""
    
    def __init__(self, config: Config):
        self.config = config
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = self._generate_secret_key()
        
        # In-memory storage (in production, use persistent storage)
        self.active_tokens: Dict[str, AccessToken] = {}
        self.access_policies: Dict[str, AccessPolicy] = {}
        self.audit_logs: List[AccessAuditLog] = []
        
        # Rate limiting
        self.request_counts: Dict[str, List[datetime]] = {}
    
    def _generate_secret_key(self) -> str:
        """Generate or load JWT secret key."""
        key_file = Path("keys/jwt_secret.key")
        
        if key_file.exists():
            return key_file.read_text().strip()
        else:
            key_file.parent.mkdir(parents=True, exist_ok=True)
            secret = secrets.token_urlsafe(32)
            key_file.write_text(secret)
            key_file.chmod(0o600)
            return secret
    
    async def initialize(self) -> None:
        """Initialize the access control system."""
        try:
            logger.info("Initializing access control system...")
            
            # Load existing policies and tokens
            await self._load_access_policies()
            await self._load_active_tokens()
            
            # Start cleanup tasks
            asyncio.create_task(self._cleanup_expired_tokens())
            asyncio.create_task(self._cleanup_old_audit_logs())
            
            logger.info("Access control system initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize access control system: {e}")
            raise
    
    async def _load_access_policies(self) -> None:
        """Load access policies from storage."""
        policies_file = Path("data/access_policies.json")
        
        if policies_file.exists():
            try:
                with open(policies_file, "r") as f:
                    policies_data = json.load(f)
                
                for policy_data in policies_data:
                    policy = AccessPolicy(**policy_data)
                    self.access_policies[policy.dataset_name] = policy
                
                logger.debug(f"Loaded {len(self.access_policies)} access policies")
                
            except Exception as e:
                logger.error(f"Failed to load access policies: {e}")
    
    async def _load_active_tokens(self) -> None:
        """Load active tokens from storage."""
        tokens_file = Path("data/active_tokens.json")
        
        if tokens_file.exists():
            try:
                with open(tokens_file, "r") as f:
                    tokens_data = json.load(f)
                
                for token_data in tokens_data:
                    # Convert datetime strings back to datetime objects
                    token_data["created_at"] = datetime.fromisoformat(token_data["created_at"])
                    token_data["expires_at"] = datetime.fromisoformat(token_data["expires_at"])
                    if token_data["last_used"]:
                        token_data["last_used"] = datetime.fromisoformat(token_data["last_used"])
                    
                    token = AccessToken(**token_data)
                    
                    # Only load non-expired tokens
                    if token.expires_at > datetime.now():
                        self.active_tokens[token.token_id] = token
                
                logger.debug(f"Loaded {len(self.active_tokens)} active tokens")
                
            except Exception as e:
                logger.error(f"Failed to load active tokens: {e}")
    
    async def create_access_token(self, user_email: str, datasets: List[str],
                                permissions: List[str] = None,
                                expires_in: int = None) -> str:
        """Create a new access token for a user."""
        try:
            if permissions is None:
                permissions = ["read"]
            
            if expires_in is None:
                expires_in = self.config.auth_token_expiry
            
            # Generate token ID
            token_id = secrets.token_urlsafe(16)
            
            # Create token
            now = datetime.now()
            expires_at = now + timedelta(seconds=expires_in)
            
            access_token = AccessToken(
                token_id=token_id,
                user_email=user_email,
                permissions=permissions,
                datasets=datasets,
                created_at=now,
                expires_at=expires_at
            )
            
            # Store token
            self.active_tokens[token_id] = access_token
            
            # Create JWT
            jwt_payload = {
                "token_id": token_id,
                "user_email": user_email,
                "permissions": permissions,
                "datasets": datasets,
                "exp": expires_at.timestamp(),
                "iat": now.timestamp()
            }
            
            jwt_token = jwt.encode(jwt_payload, self.secret_key, algorithm="HS256")
            
            # Log token creation
            await self._log_access_event(
                user_email=user_email,
                dataset_name="*",
                action="token_created",
                token_id=token_id,
                details={"datasets": datasets, "permissions": permissions}
            )
            
            # Save tokens to storage
            await self._save_active_tokens()
            
            logger.info(f"Created access token for {user_email}")
            return jwt_token
            
        except Exception as e:
            logger.error(f"Failed to create access token: {e}")
            raise
    
    async def verify_access(self, jwt_token: str, dataset_name: str) -> bool:
        """Verify if a token has access to a specific dataset."""
        try:
            # Check rate limiting
            if not await self._check_rate_limit(jwt_token):
                logger.warning(f"Rate limit exceeded for token")
                return False
            
            # Decode JWT
            try:
                payload = jwt.decode(jwt_token, self.secret_key, algorithms=["HS256"])
            except JWTError as e:
                logger.warning(f"Invalid JWT token: {e}")
                await self._log_access_event(
                    user_email="unknown",
                    dataset_name=dataset_name,
                    action="denied",
                    details={"reason": "invalid_token"}
                )
                return False
            
            token_id = payload.get("token_id")
            user_email = payload.get("user_email")
            
            # Check if token exists and is active
            if token_id not in self.active_tokens:
                logger.warning(f"Token not found: {token_id}")
                await self._log_access_event(
                    user_email=user_email,
                    dataset_name=dataset_name,
                    action="denied",
                    token_id=token_id,
                    details={"reason": "token_not_found"}
                )
                return False
            
            access_token = self.active_tokens[token_id]
            
            # Check if token has expired
            if access_token.expires_at <= datetime.now():
                logger.warning(f"Token expired: {token_id}")
                del self.active_tokens[token_id]
                await self._log_access_event(
                    user_email=user_email,
                    dataset_name=dataset_name,
                    action="denied",
                    token_id=token_id,
                    details={"reason": "token_expired"}
                )
                return False
            
            # Check dataset access
            if dataset_name not in access_token.datasets and "*" not in access_token.datasets:
                logger.warning(f"Access denied to dataset {dataset_name} for user {user_email}")
                await self._log_access_event(
                    user_email=user_email,
                    dataset_name=dataset_name,
                    action="denied",
                    token_id=token_id,
                    details={"reason": "dataset_not_allowed"}
                )
                return False
            
            # Check access policy
            if not await self._check_access_policy(user_email, dataset_name):
                await self._log_access_event(
                    user_email=user_email,
                    dataset_name=dataset_name,
                    action="denied",
                    token_id=token_id,
                    details={"reason": "policy_violation"}
                )
                return False
            
            # Update token usage
            access_token.usage_count += 1
            access_token.last_used = datetime.now()
            
            # Log successful access
            await self._log_access_event(
                user_email=user_email,
                dataset_name=dataset_name,
                action="granted",
                token_id=token_id
            )
            
            logger.debug(f"Access granted to {dataset_name} for {user_email}")
            return True
            
        except Exception as e:
            logger.error(f"Access verification error: {e}")
            return False
    
    async def _check_rate_limit(self, jwt_token: str) -> bool:
        """Check if the token is within rate limits."""
        try:
            # Use token hash as identifier
            token_hash = hashlib.sha256(jwt_token.encode()).hexdigest()[:16]
            
            now = datetime.now()
            minute_ago = now - timedelta(minutes=1)
            
            # Clean old requests
            if token_hash in self.request_counts:
                self.request_counts[token_hash] = [
                    req_time for req_time in self.request_counts[token_hash]
                    if req_time > minute_ago
                ]
            else:
                self.request_counts[token_hash] = []
            
            # Check rate limit
            if len(self.request_counts[token_hash]) >= self.config.max_requests_per_minute:
                return False
            
            # Add current request
            self.request_counts[token_hash].append(now)
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return False
    
    async def _check_access_policy(self, user_email: str, dataset_name: str) -> bool:
        """Check if user access complies with dataset policy."""
        policy = self.access_policies.get(dataset_name)
        
        if not policy:
            # No specific policy, allow access
            return True
        
        # Check if user is allowed
        if policy.allowed_users and user_email not in policy.allowed_users:
            return False
        
        # Check access count limits (would need to track per user/dataset)
        # This is a simplified implementation
        
        return True
    
    async def create_access_policy(self, dataset_name: str, owner_email: str,
                                 allowed_users: List[str] = None,
                                 required_permissions: List[str] = None) -> None:
        """Create or update access policy for a dataset."""
        if allowed_users is None:
            allowed_users = []
        if required_permissions is None:
            required_permissions = ["read"]
        
        policy = AccessPolicy(
            dataset_name=dataset_name,
            owner_email=owner_email,
            allowed_users=allowed_users,
            required_permissions=required_permissions,
            created_at=datetime.now()
        )
        
        self.access_policies[dataset_name] = policy
        
        # Save to storage
        await self._save_access_policies()
        
        logger.info(f"Created access policy for dataset: {dataset_name}")
    
    async def _log_access_event(self, user_email: str, dataset_name: str,
                              action: str, token_id: str = None,
                              ip_address: str = None, user_agent: str = None,
                              details: Dict = None) -> None:
        """Log an access event for auditing."""
        log_entry = AccessAuditLog(
            timestamp=datetime.now(),
            user_email=user_email,
            dataset_name=dataset_name,
            action=action,
            token_id=token_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details
        )
        
        self.audit_logs.append(log_entry)
        
        # Keep only recent logs in memory
        if len(self.audit_logs) > 10000:
            self.audit_logs = self.audit_logs[-5000:]
    
    async def get_audit_logs(self, user_email: str = None,
                           dataset_name: str = None,
                           hours: int = 24) -> List[AccessAuditLog]:
        """Retrieve audit logs with optional filters."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        filtered_logs = []
        for log in self.audit_logs:
            if log.timestamp < cutoff_time:
                continue
            
            if user_email and log.user_email != user_email:
                continue
            
            if dataset_name and log.dataset_name != dataset_name:
                continue
            
            filtered_logs.append(log)
        
        return filtered_logs
    
    async def revoke_token(self, token_id: str) -> bool:
        """Revoke an access token."""
        if token_id in self.active_tokens:
            token = self.active_tokens[token_id]
            del self.active_tokens[token_id]
            
            # Log revocation
            await self._log_access_event(
                user_email=token.user_email,
                dataset_name="*",
                action="token_revoked",
                token_id=token_id
            )
            
            await self._save_active_tokens()
            logger.info(f"Revoked token: {token_id}")
            return True
        
        return False
    
    async def _cleanup_expired_tokens(self) -> None:
        """Periodic cleanup of expired tokens."""
        while True:
            try:
                now = datetime.now()
                expired_tokens = []
                
                for token_id, token in self.active_tokens.items():
                    if token.expires_at <= now:
                        expired_tokens.append(token_id)
                
                for token_id in expired_tokens:
                    del self.active_tokens[token_id]
                
                if expired_tokens:
                    logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")
                    await self._save_active_tokens()
                
                # Sleep for 1 hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Token cleanup error: {e}")
                await asyncio.sleep(300)  # Retry in 5 minutes
    
    async def _cleanup_old_audit_logs(self) -> None:
        """Periodic cleanup of old audit logs."""
        while True:
            try:
                # Keep logs for 30 days
                cutoff_time = datetime.now() - timedelta(days=30)
                
                original_count = len(self.audit_logs)
                self.audit_logs = [
                    log for log in self.audit_logs
                    if log.timestamp > cutoff_time
                ]
                
                cleaned_count = original_count - len(self.audit_logs)
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} old audit logs")
                
                # Sleep for 24 hours
                await asyncio.sleep(86400)
                
            except Exception as e:
                logger.error(f"Audit log cleanup error: {e}")
                await asyncio.sleep(3600)  # Retry in 1 hour
    
    async def _save_access_policies(self) -> None:
        """Save access policies to storage."""
        try:
            policies_file = Path("data/access_policies.json")
            policies_file.parent.mkdir(parents=True, exist_ok=True)
            
            policies_data = []
            for policy in self.access_policies.values():
                policy_dict = asdict(policy)
                policy_dict["created_at"] = policy.created_at.isoformat() if policy.created_at else None
                policies_data.append(policy_dict)
            
            with open(policies_file, "w") as f:
                json.dump(policies_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save access policies: {e}")
    
    async def _save_active_tokens(self) -> None:
        """Save active tokens to storage."""
        try:
            tokens_file = Path("data/active_tokens.json")
            tokens_file.parent.mkdir(parents=True, exist_ok=True)
            
            tokens_data = []
            for token in self.active_tokens.values():
                token_dict = asdict(token)
                token_dict["created_at"] = token.created_at.isoformat()
                token_dict["expires_at"] = token.expires_at.isoformat()
                token_dict["last_used"] = token.last_used.isoformat() if token.last_used else None
                tokens_data.append(token_dict)
            
            with open(tokens_file, "w") as f:
                json.dump(tokens_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save active tokens: {e}")