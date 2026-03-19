"""Main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Import routers
from routers import acopios, pedidos, remitos, imputaciones, reportes, spf_integration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Acopios API",
    description="Sistema de gestión de acopios para Fontela Cristales",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(acopios.router, prefix="/acopios", tags=["Acopios"])
app.include_router(pedidos.router, prefix="/pedidos", tags=["Pedidos"])
app.include_router(remitos.router, prefix="/remitos", tags=["Remitos"])
app.include_router(imputaciones.router, prefix="/imputaciones", tags=["Imputaciones"])
app.include_router(reportes.router, prefix="/reportes", tags=["Reportes"])
app.include_router(spf_integration.router, prefix="/integrations/spf", tags=["SPF Integrations"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Acopios API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
