from pathlib import Path

from fastapi.responses import FileResponse

from main import app
from shipment_ai_routes import (
    router as shipment_ai_router
)
from shipment_bulk_routes import (
    router as shipment_bulk_router
)
from shipment_pdf_routes import (
    router as shipment_pdf_router
)
from shipment_routes import (
    router as shipment_router
)


BASE_DIR = Path(__file__).resolve().parent


app.include_router(
    shipment_router
)

app.include_router(
    shipment_ai_router
)

app.include_router(
    shipment_pdf_router
)

app.include_router(
    shipment_bulk_router
)


@app.get(
    "/shipment-dashboard",
    include_in_schema=False
)
def shipment_dashboard():
    return FileResponse(
        BASE_DIR /
        "shipment_dashboard.html"
    )


@app.get(
    "/bulk-dashboard",
    include_in_schema=False
)
def bulk_dashboard():
    return FileResponse(
        BASE_DIR /
        "bulk_dashboard.html"
    )