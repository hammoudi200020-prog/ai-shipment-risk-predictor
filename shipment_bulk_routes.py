import io
import json

import pandas as pd
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile
)
from sqlalchemy.orm import Session

import models
from risk_predictor import (
    predict_shipment_delay
)
from shipment_routes import get_database


router = APIRouter(
    prefix="/shipments",
    tags=["Bulk Shipment Analysis"]
)


REQUIRED_COLUMNS = [
    "shipment_number",
    "origin",
    "destination",
    "distance_km",
    "dispatch_delay_hours",
    "days_remaining",
    "documentation_complete",
    "vehicle_available",
    "priority",
    "transport_type",
    "current_stage"
]


def convert_boolean(value):
    normalized = str(
        value
    ).strip().lower()

    if normalized in {
        "true",
        "1",
        "yes",
        "y"
    }:
        return True

    if normalized in {
        "false",
        "0",
        "no",
        "n"
    }:
        return False

    raise ValueError(
        (
            "Boolean values must be "
            "true/false, yes/no, or 1/0."
        )
    )


def clean_text(
    value,
    field_name
):
    if pd.isna(value):
        raise ValueError(
            f"{field_name} is required."
        )

    result = str(value).strip()

    if not result:
        raise ValueError(
            f"{field_name} is required."
        )

    return result


@router.post("/bulk-upload")
async def upload_and_analyze_shipments(
    file: UploadFile = File(...),
    database: Session = Depends(
        get_database
    )
):
    file_name = file.filename or ""

    if not file_name.lower().endswith(
        ".csv"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Please upload a CSV file."
            )
        )

    file_content = await file.read()

    if not file_content:
        raise HTTPException(
            status_code=400,
            detail=(
                "The uploaded CSV file "
                "is empty."
            )
        )

    maximum_file_size = (
        5 * 1024 * 1024
    )

    if len(file_content) > maximum_file_size:
        raise HTTPException(
            status_code=400,
            detail=(
                "The CSV file must be "
                "smaller than 5 MB."
            )
        )

    try:
        text_content = (
            file_content.decode(
                "utf-8-sig"
            )
        )

        data_frame = pd.read_csv(
            io.StringIO(
                text_content
            )
        )

    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail=(
                "The CSV file must use "
                "UTF-8 encoding."
            )
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not read the CSV "
                f"file: {error}"
            )
        ) from error

    data_frame.columns = [
        str(column).strip().lower()
        for column
        in data_frame.columns
    ]

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in data_frame.columns
    ]

    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing required columns: "
                + ", ".join(
                    missing_columns
                )
            )
        )

    if data_frame.empty:
        raise HTTPException(
            status_code=400,
            detail=(
                "The CSV file contains "
                "no shipment rows."
            )
        )

    if len(data_frame) > 5000:
        raise HTTPException(
            status_code=400,
            detail=(
                "A maximum of 5,000 "
                "shipments can be uploaded "
                "at once."
            )
        )

    existing_numbers = {
        item[0]
        for item in database.query(
            models.Shipment
            .shipment_number
        ).all()
    }

    uploaded_numbers = set()
    saved_shipments = []
    row_errors = []
    duplicate_count = 0

    for row_index, row in (
        data_frame.iterrows()
    ):
        csv_row_number = (
            row_index + 2
        )

        try:
            shipment_number = clean_text(
                row["shipment_number"],
                "shipment_number"
            )

            if (
                shipment_number
                in existing_numbers
                or shipment_number
                in uploaded_numbers
            ):
                duplicate_count += 1
                continue

            priority = clean_text(
                row["priority"],
                "priority"
            ).lower()

            transport_type = clean_text(
                row["transport_type"],
                "transport_type"
            ).lower()

            current_stage = clean_text(
                row["current_stage"],
                "current_stage"
            ).lower()

            allowed_priorities = {
                "low",
                "medium",
                "high"
            }

            if (
                priority
                not in allowed_priorities
            ):
                raise ValueError(
                    (
                        "priority must be low, "
                        "medium, or high."
                    )
                )

            allowed_transport_types = {
                "road",
                "air",
                "sea"
            }

            if (
                transport_type
                not in
                allowed_transport_types
            ):
                raise ValueError(
                    (
                        "transport_type must be "
                        "road, air, or sea."
                    )
                )

            allowed_stages = {
                "processing",
                "ready",
                "dispatched",
                "in_transit"
            }

            if (
                current_stage
                not in allowed_stages
            ):
                raise ValueError(
                    (
                        "current_stage must be "
                        "processing, ready, "
                        "dispatched, or "
                        "in_transit."
                    )
                )

            shipment_data = {
                "shipment_number":
                    shipment_number,

                "origin":
                    clean_text(
                        row["origin"],
                        "origin"
                    ),

                "destination":
                    clean_text(
                        row["destination"],
                        "destination"
                    ),

                "distance_km":
                    float(
                        row["distance_km"]
                    ),

                "dispatch_delay_hours":
                    int(
                        row[
                            "dispatch_delay_hours"
                        ]
                    ),

                "days_remaining":
                    int(
                        row["days_remaining"]
                    ),

                "documentation_complete":
                    convert_boolean(
                        row[
                            "documentation_complete"
                        ]
                    ),

                "vehicle_available":
                    convert_boolean(
                        row[
                            "vehicle_available"
                        ]
                    ),

                "priority":
                    priority,

                "transport_type":
                    transport_type,

                "current_stage":
                    current_stage
            }

            if (
                shipment_data[
                    "distance_km"
                ] <= 0
            ):
                raise ValueError(
                    (
                        "distance_km must be "
                        "greater than zero."
                    )
                )

            if (
                shipment_data[
                    "dispatch_delay_hours"
                ] < 0
            ):
                raise ValueError(
                    (
                        "dispatch_delay_hours "
                        "cannot be negative."
                    )
                )

            if (
                shipment_data[
                    "days_remaining"
                ] < 0
            ):
                raise ValueError(
                    (
                        "days_remaining cannot "
                        "be negative."
                    )
                )

            prediction = (
                predict_shipment_delay(
                    shipment_data
                )
            )

            shipment = models.Shipment(
                shipment_number=(
                    shipment_number
                ),
                origin=(
                    shipment_data[
                        "origin"
                    ]
                ),
                destination=(
                    shipment_data[
                        "destination"
                    ]
                ),
                distance_km=(
                    shipment_data[
                        "distance_km"
                    ]
                ),
                dispatch_delay_hours=(
                    shipment_data[
                        "dispatch_delay_hours"
                    ]
                ),
                days_remaining=(
                    shipment_data[
                        "days_remaining"
                    ]
                ),
                documentation_complete=(
                    shipment_data[
                        "documentation_complete"
                    ]
                ),
                vehicle_available=(
                    shipment_data[
                        "vehicle_available"
                    ]
                ),
                priority=priority,
                transport_type=(
                    transport_type
                ),
                current_stage=(
                    current_stage
                ),
                delay_probability=(
                    prediction[
                        "delay_probability"
                    ]
                ),
                risk_level=(
                    prediction[
                        "risk_level"
                    ]
                ),
                prediction=(
                    prediction[
                        "prediction"
                    ]
                ),
                risk_factors=json.dumps(
                    prediction[
                        "risk_factors"
                    ],
                    ensure_ascii=False
                ),
                recommended_actions=(
                    json.dumps(
                        prediction[
                            "recommended_actions"
                        ],
                        ensure_ascii=False
                    )
                ),
                actual_status="unknown"
            )

            database.add(
                shipment
            )

            uploaded_numbers.add(
                shipment_number
            )

            saved_shipments.append(
                {
                    "shipment_number":
                        shipment_number,

                    "delay_probability":
                        prediction[
                            "delay_probability"
                        ],

                    "risk_level":
                        prediction[
                            "risk_level"
                        ],

                    "prediction":
                        prediction[
                            "prediction"
                        ]
                }
            )

        except Exception as error:
            row_errors.append(
                {
                    "row":
                        csv_row_number,

                    "error":
                        str(error)
                }
            )

    try:
        database.commit()

    except Exception as error:
        database.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not save the "
                "shipment results: "
                f"{error}"
            )
        ) from error

    saved_shipments.sort(
        key=lambda item: (
            item[
                "delay_probability"
            ]
        ),
        reverse=True
    )

    risk_counts = {
        "high":
            sum(
                item["risk_level"] == "High"
                for item
                in saved_shipments
            ),

        "medium":
            sum(
                item["risk_level"] == "Medium"
                for item
                in saved_shipments
            ),

        "low":
            sum(
                item["risk_level"] == "Low"
                for item
                in saved_shipments
            )
    }

    return {
        "message":
            (
                "Bulk shipment analysis "
                "completed."
            ),

        "file_name":
            file_name,

        "rows_received":
            len(data_frame),

        "shipments_saved":
            len(saved_shipments),

        "duplicates_skipped":
            duplicate_count,

        "rows_with_errors":
            len(row_errors),

        "risk_counts":
            risk_counts,

        "highest_risk_shipments":
            saved_shipments[:10],

        "row_errors":
            row_errors[:50]
    }