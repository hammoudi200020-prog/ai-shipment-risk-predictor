from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)
from sqlalchemy.orm import Session

import ai_agent
import models
from shipment_routes import (
    get_database,
    shipment_to_dictionary
)


router = APIRouter(
    prefix="/shipments",
    tags=["AI Shipment Analysis"]
)


@router.post(
    "/{shipment_id}/ai-analysis"
)
def generate_ai_shipment_analysis(
    shipment_id: int,
    database: Session = Depends(
        get_database
    )
):
    shipment = database.query(
        models.Shipment
    ).filter(
        models.Shipment.id
        == shipment_id
    ).first()

    if shipment is None:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    shipment_data = (
        shipment_to_dictionary(
            shipment
        )
    )

    try:
        analysis = (
            ai_agent
            .generate_shipment_risk_analysis(
                shipment_data
            )
        )

        return {
            "shipment_id":
                shipment.id,
            "shipment_number":
                shipment.shipment_number,
            "delay_probability":
                shipment.delay_probability,
            "risk_level":
                shipment.risk_level,
            "ai_analysis":
                analysis.model_dump()
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "AI analysis service error: "
                f"{str(error)}"
            )
        )