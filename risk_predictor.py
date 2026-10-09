from pathlib import Path

import joblib
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

MODEL_FILE = (
    BASE_DIR /
    "shipment_delay_model.joblib"
)


def load_model_package():
    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            "The shipment delay model was not found. "
            "Run train_model.py first."
        )

    return joblib.load(
        MODEL_FILE
    )


def identify_risk_factors(
    shipment_data: dict
):
    risk_factors = []

    if (
        shipment_data[
            "documentation_complete"
        ] == 0
    ):
        risk_factors.append(
            "Shipping documents are incomplete."
        )

    if (
        shipment_data[
            "vehicle_available"
        ] == 0
    ):
        risk_factors.append(
            "A transport vehicle is not currently available."
        )

    if (
        shipment_data[
            "dispatch_delay_hours"
        ] >= 8
    ):
        risk_factors.append(
            "The shipment already has a significant "
            "dispatch delay."
        )

    elif (
        shipment_data[
            "dispatch_delay_hours"
        ] >= 4
    ):
        risk_factors.append(
            "The shipment has started to experience "
            "a dispatch delay."
        )

    if (
        shipment_data[
            "days_remaining"
        ] <= 2
    ):
        risk_factors.append(
            "Very little time remains before "
            "the delivery deadline."
        )

    elif (
        shipment_data[
            "days_remaining"
        ] <= 4
    ):
        risk_factors.append(
            "The remaining delivery time is limited."
        )

    if (
        shipment_data[
            "distance_km"
        ] >= 800
    ):
        risk_factors.append(
            "The shipment must travel a long distance."
        )

    if (
        shipment_data[
            "current_stage"
        ] == "processing"
        and shipment_data[
            "days_remaining"
        ] <= 3
    ):
        risk_factors.append(
            "The shipment is still being processed "
            "close to its deadline."
        )

    if not risk_factors:
        risk_factors.append(
            "No major operational risk factors "
            "were detected."
        )

    return risk_factors


def create_recommended_actions(
    shipment_data: dict,
    risk_level: str
):
    actions = []

    if (
        shipment_data[
            "documentation_complete"
        ] == 0
    ):
        actions.append(
            "Complete and verify the missing "
            "shipping documents immediately."
        )

    if (
        shipment_data[
            "vehicle_available"
        ] == 0
    ):
        actions.append(
            "Assign an available vehicle or "
            "contact an alternative carrier."
        )

    if (
        shipment_data[
            "dispatch_delay_hours"
        ] >= 4
    ):
        actions.append(
            "Escalate the dispatch delay to "
            "the operations supervisor."
        )

    if (
        shipment_data[
            "days_remaining"
        ] <= 2
    ):
        actions.append(
            "Prioritize this shipment and monitor "
            "its progress closely."
        )

    if (
        shipment_data[
            "distance_km"
        ] >= 800
    ):
        actions.append(
            "Confirm the route, transport schedule, "
            "and estimated arrival time."
        )

    if risk_level == "High":
        actions.append(
            "Notify management and prepare a "
            "delay mitigation plan."
        )

    elif risk_level == "Medium":
        actions.append(
            "Review the shipment again within "
            "the next operational shift."
        )

    if not actions:
        actions.append(
            "Continue normal monitoring until delivery."
        )

    return actions


def predict_shipment_delay(
    shipment_data: dict
):
    model_package = load_model_package()

    model = model_package[
        "model"
    ]

    feature_columns = model_package[
        "feature_columns"
    ]

    shipment_frame = pd.DataFrame(
        [
            shipment_data
        ],
        columns=feature_columns
    )

    delay_probability = float(
        model.predict_proba(
            shipment_frame
        )[0][1]
    )

    probability_percentage = round(
        delay_probability * 100,
        1
    )

    if probability_percentage >= 70:
        risk_level = "High"

    elif probability_percentage >= 40:
        risk_level = "Medium"

    else:
        risk_level = "Low"

    predicted_result = (
        "Likely Delayed"
        if probability_percentage >= 50
        else "Likely On Time"
    )

    risk_factors = identify_risk_factors(
        shipment_data
    )

    recommended_actions = (
        create_recommended_actions(
            shipment_data,
            risk_level
        )
    )

    return {
        "delay_probability":
            probability_percentage,
        "risk_level":
            risk_level,
        "prediction":
            predicted_result,
        "risk_factors":
            risk_factors,
        "recommended_actions":
            recommended_actions,
        "model_metrics":
            model_package["metrics"],
        "data_source":
            model_package["data_source"]
    }


if __name__ == "__main__":
    example_shipment = {
        "distance_km": 950,
        "dispatch_delay_hours": 10,
        "days_remaining": 1,
        "documentation_complete": 0,
        "vehicle_available": 0,
        "priority": "high",
        "transport_type": "road",
        "current_stage": "processing"
    }

    result = predict_shipment_delay(
        example_shipment
    )

    print("")
    print("Shipment Delay Prediction")
    print("-------------------------")

    print(
        "Delay probability:",
        f"{result['delay_probability']}%"
    )

    print(
        "Risk level:",
        result["risk_level"]
    )

    print(
        "Prediction:",
        result["prediction"]
    )

    print("")
    print("Risk factors:")

    for factor in result[
        "risk_factors"
    ]:
        print(
            f"- {factor}"
        )

    print("")
    print("Recommended actions:")

    for action in result[
        "recommended_actions"
    ]:
        print(
            f"- {action}"
        )

    print("")