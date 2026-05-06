"""
认证中间件
提供JWT认证和用户会话管理
"""
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from backend.src.config.settings import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """
    认证中间件
    处理JWT令牌验证和用户身份识别
    """

    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire = settings.ACCESS_TOKEN_EXPIRE_MINUTES

    def create_access_token(
        self,
        user_id: str,
        username: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        创建访问令牌

        Args:
            user_id: 用户ID
            username: 用户名
            extra_data: 额外数据

        Returns:
            JWT访问令牌
        """
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire)
        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
        }

        if username:
            payload["username"] = username

        if extra_data:
            payload.update(extra_data)

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def create_refresh_token(self, user_id: str) -> str:
        """
        创建刷新令牌

        Args:
            user_id: 用户ID

        Returns:
            JWT刷新令牌
        """
        expire = datetime.utcnow() + timedelta(days=7)
        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        验证令牌

        Args:
            token: JWT令牌

        Returns:
            解码后的payload或None
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.warning(f"令牌验证失败: {e}")
            return None

    def get_user_from_token(self, token: str) -> Optional[str]:
        """
        从令牌获取用户ID

        Args:
            token: JWT令牌

        Returns:
            用户ID或None
        """
        payload = self.verify_token(token)
        if payload:
            return payload.get("sub")
        return None

    async def __call__(self, request: Request) -> Optional[str]:
        """
        中间件调用入口

        Args:
            request: HTTP请求

        Returns:
            用户ID或None
        """
        # 跳过健康检查等不需要认证的路径
        if self._is_public_path(request.url.path):
            return None

        # 从Authorization header获取令牌
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = auth_header

        if not token:
            return None

        user_id = self.get_user_from_token(token)
        if user_id:
            request.state.user_id = user_id
            return user_id

        return None

    def _is_public_path(self, path: str) -> bool:
        """检查是否为公开路径"""
        public_paths = [
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
        ]
        return any(path.startswith(p) for p in public_paths)


# 全局认证中间件实例
auth_middleware = AuthMiddleware()


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """
    获取当前用户依赖

    Args:
        request: HTTP请求
        credentials: Bearer令牌凭据

    Returns:
        用户ID或None

    Raises:
        HTTPException: 认证失败
    """
    # 公开路径跳过认证
    public_paths = ["/health", "/metrics", "/docs", "/openapi.json", "/redoc"]
    if any(request.url.path.startswith(p) for p in public_paths):
        return None

    if not credentials:
        raise HTTPException(status_code=401, detail="缺少认证凭据")

    token = credentials.credentials
    user_id = auth_middleware.get_user_from_token(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="无效的认证凭据")

    request.state.user_id = user_id
    return user_id


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """
    获取当前用户（可选，不强制认证）

    Returns:
        用户ID或None
    """
    public_paths = ["/health", "/metrics", "/docs", "/openapi.json", "/redoc"]
    if any(request.url.path.startswith(p) for p in public_paths):
        return None

    if not credentials:
        return None

    token = credentials.credentials
    user_id = auth_middleware.get_user_from_token(token)
    if user_id:
        request.state.user_id = user_id
    return user_id


def require_auth(func):
    """
    认证装饰器
    要求用户已认证才能访问

    Args:
        func: 要装饰的函数

    Returns:
        装饰后的函数
    """
    async def wrapper(*args, **kwargs):
        request = kwargs.get("request") or args[0] if args else None
        if not request or not hasattr(request, "state") or not getattr(request.state, "user_id", None):
            raise HTTPException(status_code=401, detail="需要认证")
        return await func(*args, **kwargs)
    return wrapper
