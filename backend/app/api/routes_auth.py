# app/api/routes_auth.py
from fastapi import APIRouter, Depends, Request
from loguru import logger

from app.models.auth_models import LoginRequest, TokenResponse
from app.services.auth_service import login, get_current_user, verify_token_health

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
async def login_endpoint(login_data: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    
    logger.info(f"Login request received | Username: {login_data.username} | IP: {client_ip}")
    
    result = await login(login_data, request)
    
    logger.info(f"Login response sent | Username: {login_data.username} | Success: True | IP: {client_ip}")
    
    return result

@router.get("/me")
async def me(request: Request, current_user: str = Depends(get_current_user)):
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    logger.bind(request_id=request_id, user_id=current_user).info(
        "User info request"
    )
    
    return {
        "username": current_user,
        "authenticated": True,
        "request_id": request_id
    }

@router.get("/health")
async def auth_health(request: Request):
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    logger.bind(request_id=request_id).info("Auth health check requested")
    
    health_status = verify_token_health()
    
    logger.bind(request_id=request_id).info(f"Auth health check result: {health_status['status']}")
    
    return health_status

@router.post("/refresh")
async def refresh_token(request: Request, current_user: str = Depends(get_current_user)):
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    logger.bind(request_id=request_id, user_id=current_user).info("Token refresh requested")
    return {
        "message": "Token refresh endpoint - implement as needed",
        "user": current_user,
        "request_id": request_id
    }

@router.post("/logout")
async def logout(request: Request, current_user: str = Depends(get_current_user)):
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    logger.bind(request_id=request_id, user_id=current_user).info("Logout requested")
    return {
        "message": "Logout successful",
        "user": current_user,
        "request_id": request_id
    }