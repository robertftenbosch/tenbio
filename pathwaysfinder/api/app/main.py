from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routes import parts, optimize, igem

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Tenbio Pathways API",
    description="API for genetic parts and pathway design",
    version="0.1.0",
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(parts.router)
app.include_router(optimize.router)
app.include_router(igem.router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
