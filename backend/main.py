"""
FastAPI Application - Backend Server
Provides REST API endpoints for AI agents including exception analysis
"""
import logging
import os
import sys
from contextlib import asynccontextmanager

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import routers
from api.routes import exception
from api.routes import dashboard


# ============================================================================
# Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info("Starting FastAPI application...")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    
    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not set - AI features may not work")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI application...")


# ============================================================================
# Create FastAPI Application
# ============================================================================

app = FastAPI(
    title="AI Agent Backend API",
    description="Backend API for AI-powered exception analysis and quotation management",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


# ============================================================================
# Middleware Configuration
# ============================================================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Register Routers
# ============================================================================

# Register exception analysis router
app.include_router(exception.router)

# Register dashboard router (业务总览 + 可视化)
app.include_router(dashboard.router)

logger.info("Registered exception analysis router at /api/exception")
logger.info("Registered dashboard router at /dashboard")


# ============================================================================
# Root Endpoints
# ============================================================================

@app.get("/")
async def root():
    """
    Root endpoint - redirects to the dashboard
    """
    return {
        "message": "AI Agent Backend API",
        "version": "1.0.0",
        "dashboard": "/dashboard",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    
    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": "ai-agent-backend"
    }


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("ENVIRONMENT", "development") == "development"
    
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"Reload mode: {reload}")
    
    # Run the application
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )
