"""
API Middleware - Request/response middleware for FastAPI

Provides production-ready middleware for:
- CORS handling
- Request logging
- Response timing
- Error handling
- Rate limiting (using slowapi)

Uses FastAPI's built-in middleware system.
"""

import time
import logging
from typing import Callable, Optional, List
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Setup logging
logger = logging.getLogger(__name__)


# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


def setup_cors(app: FastAPI, allowed_origins: Optional[List[str]] = None):
    """
    Setup CORS middleware.
    
    Args:
        app: FastAPI application instance
        allowed_origins: List of allowed origins. If None, allows all origins.
        
    Usage:
        from api.middleware import setup_cors
        
        setup_cors(app, allowed_origins=[
            "http://localhost:3000",
            "https://yourdomain.com"
        ])
    """
    origins = allowed_origins or ["*"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    logger.info(f"CORS middleware configured with origins: {origins}")


def setup_rate_limiting(app: FastAPI):
    """
    Setup rate limiting middleware using slowapi.
    
    Args:
        app: FastAPI application instance
        
    Usage:
        from api.middleware import setup_rate_limiting
        
        setup_rate_limiting(app)
        
    Default limit: 100 requests per minute per IP
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    logger.info("Rate limiting middleware configured (100/minute)")


async def request_logging_middleware(request: Request, call_next: Callable):
    """
    Middleware to log all incoming requests.
    
    Logs:
    - Request method and path
    - Client IP address
    - Request processing time
    - Response status code
    
    Args:
        request: Incoming request
        call_next: Next middleware or endpoint
        
    Returns:
        Response from next middleware/endpoint
    """
    # Start timing
    start_time = time.time()
    
    # Get client info
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    
    # Log request
    logger.info(f"Request: {method} {path} from {client_ip}")
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Add custom header
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log response
        logger.info(
            f"Response: {method} {path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        
        return response
        
    except Exception as e:
        # Log error
        process_time = time.time() - start_time
        logger.error(
            f"Error: {method} {path} - "
            f"Error: {str(e)} - "
            f"Time: {process_time:.3f}s"
        )
        raise


async def error_handling_middleware(request: Request, call_next: Callable):
    """
    Middleware to handle errors gracefully.
    
    Catches unhandled exceptions and returns proper JSON responses.
    
    Args:
        request: Incoming request
        call_next: Next middleware or endpoint
        
    Returns:
        Response or error response
    """
    try:
        response = await call_next(request)
        return response
        
    except RateLimitExceeded:
        # Let slowapi handle rate limit errors
        raise
        
    except ValueError as e:
        # Handle validation errors
        logger.warning(f"Validation error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "error": "Validation Error",
                "message": str(e)
            }
        )
        
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later."
            }
        )


def setup_middleware(
    app: FastAPI,
    enable_cors: bool = True,
    allowed_origins: Optional[List[str]] = None,
    enable_rate_limiting: bool = True,
    enable_logging: bool = True,
    enable_error_handling: bool = True
):
    """
    Setup all middleware for the FastAPI application.
    
    Args:
        app: FastAPI application instance
        enable_cors: Enable CORS middleware
        allowed_origins: List of allowed CORS origins
        enable_rate_limiting: Enable rate limiting
        enable_logging: Enable request logging
        enable_error_handling: Enable error handling
        
    Usage:
        from fastapi import FastAPI
        from api.middleware import setup_middleware
        
        app = FastAPI()
        setup_middleware(
            app,
            allowed_origins=["http://localhost:3000"]
        )
        
    This is the recommended way to setup all middleware at once.
    """
    # Error handling (should be first to catch all errors)
    if enable_error_handling:
        app.middleware("http")(error_handling_middleware)
        logger.info("Error handling middleware enabled")
    
    # Request logging
    if enable_logging:
        app.middleware("http")(request_logging_middleware)
        logger.info("Request logging middleware enabled")
    
    # CORS
    if enable_cors:
        setup_cors(app, allowed_origins)
    
    # Rate limiting
    if enable_rate_limiting:
        setup_rate_limiting(app)
    
    logger.info("All middleware configured successfully")


# Decorator for rate limiting specific endpoints
def rate_limit(limit_string: str):
    """
    Decorator to add rate limiting to specific endpoints.
    
    Args:
        limit_string: Rate limit string (e.g., "10/minute", "100/hour")
        
    Usage:
        from api.middleware import rate_limit, limiter
        
        @app.post("/api/endpoint")
        @limiter.limit("10/minute")
        async def endpoint():
            return {"message": "Limited to 10 requests per minute"}
    
    Note: Requires limiter to be added to app.state in setup_rate_limiting()
    """
    return limiter.limit(limit_string)


# Custom middleware for authentication (placeholder)
async def auth_middleware(request: Request, call_next: Callable):
    """
    Authentication middleware (placeholder).
    
    Add your authentication logic here.
    
    Example:
        - Check for API key in headers
        - Verify JWT tokens
        - Validate session cookies
        
    Args:
        request: Incoming request
        call_next: Next middleware or endpoint
        
    Returns:
        Response or 401 Unauthorized
    """
    # Example: Check for API key
    # api_key = request.headers.get("X-API-Key")
    # if not api_key or not is_valid_api_key(api_key):
    #     return JSONResponse(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         content={"error": "Unauthorized", "message": "Invalid or missing API key"}
    #     )
    
    # For now, allow all requests
    response = await call_next(request)
    return response


# Request ID middleware
async def request_id_middleware(request: Request, call_next: Callable):
    """
    Add unique request ID to each request.
    
    Useful for tracing requests through logs.
    
    Args:
        request: Incoming request
        call_next: Next middleware or endpoint
        
    Returns:
        Response with X-Request-ID header
    """
    import uuid
    
    # Generate or extract request ID
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    # Process request
    response = await call_next(request)
    
    # Add request ID to response
    response.headers["X-Request-ID"] = request_id
    
    return response


# Export commonly used items
__all__ = [
    "setup_middleware",
    "setup_cors",
    "setup_rate_limiting",
    "limiter",
    "rate_limit",
    "request_logging_middleware",
    "error_handling_middleware",
    "auth_middleware",
    "request_id_middleware",
]
