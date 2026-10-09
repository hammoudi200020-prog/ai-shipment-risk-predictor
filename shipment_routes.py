import json
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from database import SessionLocal
from risk_predictor import (
    predict_shipment_delay
)


router = APIRouter(
    prefix="/shipments",
    tags=["Shipment Risk Prediction"]
)


class ShipmentCreate(BaseModel):
    shipment_number: str = Field(
        min_length=1,
        max_length=100
    )

    origin: str = Field(
        min_length=1,
        max_length=150
    )

    destination: str = Field(
        min_length=1,
        max_length=150
    )

    distance_km: float = Field(
        gt=0
    )

    dispatch_delay_hours: int = Field(
        default=0,
        ge=0
    )

    days_remaining: int = Field(
        ge=0
    )

    documentation_complete: bool = True

    vehicle_available: bool = True

    priority: Literal[
        "low",
        "medium",
        "high"
    ] = "medium"

    transport_type: Literal[
        "road",
        "air",
        "sea"
    ] = "road"

    current_stage: Literal[
        "processing",
        "ready",
        "dispatched",
        "in_transit"
    ] = "processing"


class ShipmentStatusUpdate(BaseModel):
    actual_status: Literal[
        "unknown",
        "on_time",
        "delayed",
        "delivered"
    ]


def get_database():
    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()


def shipment_to_dictionary(
    shipment: models.Shipment
):
    try:
        risk_factors = json.loads(
            shipment.risk_factors or "[]"
        )

    except json.JSONDecodeError:
        risk_factors = []

    try:
        recommended_actions = json.loads(
            shipment.recommended_actions or "[]"
        )

    except json.JSONDecodeError:
        recommended_actions = []

    return {
        "id":
            shipment.id,
        "shipment_number":
            shipment.shipment_number,
        "origin":
            shipment.origin,
        "destination":
            shipment.destination,
        "distance_km":
            shipment.distance_km,
        "dispatch_delay_hours":
            shipment.dispatch_delay_hours,
        "days_remaining":
            shipment.days_remaining,
        "documentation_complete":
            shipment.documentation_complete,
        "vehicle_available":
            shipment.vehicle_available,
        "priority":
            shipment.priority,
        "transport_type":
            shipment.transport_type,
        "current_stage":
            shipment.current_stage,
        "delay_probability":
            shipment.delay_probability,
        "risk_level":
            shipment.risk_level,
        "prediction":
            shipment.prediction,
        "risk_factors":
            risk_factors,
        "recommended_actions":
            recommended_actions,
        "actual_status":
            shipment.actual_status,
        "created_at":
            (
                shipment.created_at.isoformat()
                if shipment.created_at
                else None
            )
    }


@router.post("/predict")
def predict_and_save_shipment(
    shipment: ShipmentCreate,
    database: Session = Depends(
        get_database
    )
):
    existing_shipment = database.query(
        models.Shipment
    ).filter(
        models.Shipment.shipment_number
        == shipment.shipment_number.strip()
    ).first()

    if existing_shipment:
        raise HTTPException(
            status_code=409,
            detail=(
                "A shipment with this number "
                "already exists"
            )
        )

    prediction_input = {
        "distance_km":
            shipment.distance_km,
        "dispatch_delay_hours":
            shipment.dispatch_delay_hours,
        "days_remaining":
            shipment.days_remaining,
        "documentation_complete":
            int(
                shipment.documentation_complete
            ),
        "vehicle_available":
            int(
                shipment.vehicle_available
            ),
        "priority":
            shipment.priority,
        "transport_type":
            shipment.transport_type,
        "current_stage":
            shipment.current_stage
    }

    try:
        prediction_result = (
            predict_shipment_delay(
                prediction_input
            )
        )

        new_shipment = models.Shipment(
            shipment_number=(
                shipment.shipment_number.strip()
            ),
            origin=shipment.origin.strip(),
            destination=(
                shipment.destination.strip()
            ),
            distance_km=shipment.distance_km,
            dispatch_delay_hours=(
                shipment.dispatch_delay_hours
            ),
            days_remaining=(
                shipment.days_remaining
            ),
            documentation_complete=(
                shipment.documentation_complete
            ),
            vehicle_available=(
                shipment.vehicle_available
            ),
            priority=shipment.priority,
            transport_type=(
                shipment.transport_type
            ),
            current_stage=(
                shipment.current_stage
            ),
            delay_probability=(
                prediction_result[
                    "delay_probability"
                ]
            ),
            risk_level=(
                prediction_result[
                    "risk_level"
                ]
            ),
            prediction=(
                prediction_result[
                    "prediction"
                ]
            ),
            risk_factors=json.dumps(
                prediction_result[
                    "risk_factors"
                ],
                ensure_ascii=False
            ),
            recommended_actions=json.dumps(
                prediction_result[
                    "recommended_actions"
                ],
                ensure_ascii=False
            ),
            actual_status="unknown"
        )

        database.add(
            new_shipment
        )

        database.commit()
        database.refresh(
            new_shipment
        )

        return {
            "message": (
                "Shipment risk predicted "
                "and saved successfully"
            ),
            "shipment":
                shipment_to_dictionary(
                    new_shipment
                ),
            "model_information": {
                "metrics":
                    prediction_result[
                        "model_metrics"
                    ],
                "data_source":
                    prediction_result[
                        "data_source"
                    ]
            }
        }

    except IntegrityError:
        database.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "A shipment with this number "
                "already exists"
            )
        )

    except Exception as error:
        database.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Prediction service error: "
                f"{str(error)}"
            )
        )


@router.get("")
def get_shipments(
    database: Session = Depends(
        get_database
    )
):
    shipments = database.query(
        models.Shipment
    ).order_by(
        models.Shipment.id.desc()
    ).all()

    return [
        shipment_to_dictionary(
            shipment
        )
        for shipment in shipments
    ]


@router.get("/summary")
def get_shipment_risk_summary(
    database: Session = Depends(
        get_database
    )
):
    total_shipments = database.query(
        models.Shipment
    ).count()

    low_risk = database.query(
        models.Shipment
    ).filter(
        models.Shipment.risk_level
        == "Low"
    ).count()

    medium_risk = database.query(
        models.Shipment
    ).filter(
        models.Shipment.risk_level
        == "Medium"
    ).count()

    high_risk = database.query(
        models.Shipment
    ).filter(
        models.Shipment.risk_level
        == "High"
    ).count()

    actually_delayed = database.query(
        models.Shipment
    ).filter(
        models.Shipment.actual_status
        == "delayed"
    ).count()

    average_probability = database.query(
        func.avg(
            models.Shipment.delay_probability
        )
    ).scalar()

    return {
        "total_shipments":
            total_shipments,
        "low_risk":
            low_risk,
        "medium_risk":
            medium_risk,
        "high_risk":
            high_risk,
        "actually_delayed":
            actually_delayed,
        "average_delay_probability":
            round(
                average_probability or 0,
                1
            )
    }


@router.get("/{shipment_id}")
def get_shipment(
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

    return shipment_to_dictionary(
        shipment
    )


@router.patch(
    "/{shipment_id}/actual-status"
)
def update_actual_status(
    shipment_id: int,
    update: ShipmentStatusUpdate,
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

    shipment.actual_status = (
        update.actual_status
    )

    database.commit()
    database.refresh(
        shipment
    )

    return shipment_to_dictionary(
        shipment
    )


@router.delete("/{shipment_id}")
def delete_shipment(
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

    database.delete(
        shipment
    )

    database.commit()

    return {
        "message":
            "Shipment deleted successfully"
    }