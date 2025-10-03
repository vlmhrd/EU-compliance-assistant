# app/services/auth_service.py
import hashlib, secrets
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer
from loguru import logger

from app.models.auth_models import LoginRequest, TokenResponse
from app.config import settings
from app.core.error_handler import AuthenticationError
from app.core.logging_config import LoggingConfig

security = HTTPBasic()
security_jwt = HTTPBearer()

def hash_password_with_salt(password: str) -> str:
    try:
        return hashlib.sha256((password + settings.PASSWORD_SALT).encode("utf-8")).hexdigest()
    except Exception as e:
        logger.error(f"Password hashing failed: {str(e)}")
        raise AuthenticationError("Authentication processing error")

def create_access_token(username: str) -> str:
    try:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        data = {"sub": username, "exp": expire, "iat": datetime.utcnow()}
        token = jwt.encode(data, settings.SECRET_KEY, algorithm="HS256")
        
        logger.info(f"Access token created for user: {username} | Expires: {expire}")
        return token
        
    except Exception as e:
        logger.error(f"Token creation failed for user {username}: {str(e)}")
        raise AuthenticationError("Token creation failed")

def verify_jwt_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        
        if not username:
            logger.warning("Token verification failed: missing username in payload")
            raise AuthenticationError("Invalid token: missing user information")
        
        exp = payload.get("exp")
        if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
            logger.warning(f"Token verification failed: expired token for user {username}")
            raise AuthenticationError("Token has expired")
        
        return username
        
    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        raise AuthenticationError("Invalid or expired token")
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise AuthenticationError("Token verification failed")

def verify_credentials(username: str, password: str, ip_address: str = None) -> bool:
    try:
        entered_password_hash = hash_password_with_salt(password)
        correct_password_hash = hash_password_with_salt(settings.ADMIN_PASSWORD)

        is_correct_username = secrets.compare_digest(username, settings.ADMIN_USERNAME)
        is_correct_password = secrets.compare_digest(entered_password_hash, correct_password_hash)
        
        is_valid = is_correct_username and is_correct_password
        
        LoggingConfig.log_auth_attempt(
            username=username,
            success=is_valid,
            ip_address=ip_address
        )
        
        if not is_valid:
            logger.warning(f"Failed authentication attempt for user: {username} | IP: {ip_address}")
        else:
            logger.info(f"Successful authentication for user: {username} | IP: {ip_address}")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Credential verification error for user {username}: {str(e)}")
        LoggingConfig.log_auth_attempt(
            username=username,
            success=False,
            ip_address=ip_address
        )
        return False

def get_client_ip(request: Request = None) -> str:
    if not request:
        return "unknown"
    
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    if hasattr(request, "client") and request.client:
        return request.client.host
    
    return "unknown"

def get_current_user(credentials=Depends(security_jwt)) -> str:
    try:
        username = verify_jwt_token(credentials.credentials)
        return username
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def login(login_data: LoginRequest, request: Request = None) -> TokenResponse:
    client_ip = get_client_ip(request)
    
    try:
        logger.info(f"Login attempt for user: {login_data.username} | IP: {client_ip}")
        
        if not login_data.username or not login_data.password:
            raise AuthenticationError("Username and password are required")
        
        if len(login_data.username) > 100 or len(login_data.password) > 1000:
            raise AuthenticationError("Invalid credentials format")
        
        if not verify_credentials(login_data.username, login_data.password, client_ip):
            import asyncio
            await asyncio.sleep(1)
            raise AuthenticationError("Invalid username or password")

        token = create_access_token(login_data.username)
        
        logger.info(f"Login successful for user: {login_data.username} | IP: {client_ip}")
        
        return TokenResponse(access_token=token, token_type="bearer")
        
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    except Exception as e:
        logger.error(f"Login error for user {login_data.username}: {str(e)} | IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service temporarily unavailable"
        )

def verify_token_health() -> dict:
    try:
        test_username = "health_check"
        test_token = create_access_token(test_username)
        verified_username = verify_jwt_token(test_token)
        
        if verified_username == test_username:
            return {
                "status": "healthy",
                "message": "JWT token system operational"
            }
        else:
            return {
                "status": "unhealthy", 
                "message": "Token verification mismatch"
            }
            
    except Exception as e:
        logger.error(f"Auth health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "message": f"Auth system error: {str(e)}"
        }