"""
Example route module demonstrating the new backend architecture.
New features should follow this pattern instead of adding to server.py.

To use this route:
1. Import in server.py: from routes.example import router as example_router
2. Include router: app.include_router(example_router, prefix="/api")

This keeps server.py clean while allowing modular feature development.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel

# Router with prefix and tags for API documentation
router = APIRouter(prefix="/example", tags=["Example"])


class ExampleResponse(BaseModel):
    """Example response model"""
    message: str
    data: Optional[dict] = None


@router.get("/health", response_model=ExampleResponse)
async def example_health():
    """
    Example health check endpoint.
    
    This demonstrates how to create new endpoints in modular route files.
    """
    return ExampleResponse(
        message="Example module is healthy",
        data={"module": "example", "status": "ok"}
    )


# Additional endpoints would go here following the same pattern
