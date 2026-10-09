from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = BASE_DIR / "shipment_training_data.csv"
MODEL_FILE = BASE_DIR / "shipment_delay_model.joblib"

RANDOM_SEED = 42
NUMBER_OF_SHIPMENTS = 3000


def create_synthetic_shipment_data():
    random_generator = np.random.default_rng(
        RANDOM_SEED
    )

    distance_km = random_generator.integers(
        20,
        1201,
        NUMBER_OF_SHIPMENTS
    )

    dispatch_delay_hours = random_generator.integers(
        0,
        19,
        NUMBER_OF_SHIPMENTS
    )

    days_remaining = random_generator.integers(
        1,
        11,
        NUMBER_OF_SHIPMENTS
    )

    documentation_complete = random_generator.choice(
        [0, 1],
        size=NUMBER_OF_SHIPMENTS,
        p=[0.22, 0.78]
    )

    vehicle_available = random_generator.choice(
        [0, 1],
        size=NUMBER_OF_SHIPMENTS,
        p=[0.15, 0.85]
    )

    priority = random_generator.choice(
        ["low", "medium", "high"],
        size=NUMBER_OF_SHIPMENTS,
        p=[0.25, 0.50, 0.25]
    )

    transport_type = random_generator.choice(
        ["road", "air", "sea"],
        size=NUMBER_OF_SHIPMENTS,
        p=[0.55, 0.20, 0.25]
    )

    current_stage = random_generator.choice(
        [
            "processing",
            "ready",
            "dispatched",
            "in_transit"
        ],
        size=NUMBER_OF_SHIPMENTS,
        p=[0.25, 0.20, 0.20, 0.35]
    )

    risk_score = (
        -2.5
        + distance_km * 0.003
        + dispatch_delay_hours * 0.25
        - days_remaining * 0.40
        + (1 - documentation_complete) * 1.50
        + (1 - vehicle_available) * 1.30
    )

    risk_score += np.where(
        transport_type == "sea",
        0.40,
        0.0
    )

    risk_score += np.where(
        transport_type == "road",
        0.20,
        0.0
    )

    risk_score += np.where(
        transport_type == "air",
        -0.20,
        0.0
    )

    risk_score += np.where(
        current_stage == "processing",
        0.80,
        0.0
    )

    risk_score += np.where(
        current_stage == "ready",
        0.35,
        0.0
    )

    risk_score += np.where(
        current_stage == "dispatched",
        0.10,
        0.0
    )

    risk_score += np.where(
        current_stage == "in_transit",
        -0.20,
        0.0
    )

    risk_score += np.where(
        priority == "high",
        0.15,
        0.0
    )

    random_noise = random_generator.normal(
        0,
        0.45,
        NUMBER_OF_SHIPMENTS
    )

    risk_score += random_noise

    delay_probability = 1 / (
        1 + np.exp(-risk_score)
    )

    delayed = random_generator.binomial(
        1,
        delay_probability
    )

    shipment_data = pd.DataFrame({
        "distance_km": distance_km,
        "dispatch_delay_hours": dispatch_delay_hours,
        "days_remaining": days_remaining,
        "documentation_complete":
            documentation_complete,
        "vehicle_available": vehicle_available,
        "priority": priority,
        "transport_type": transport_type,
        "current_stage": current_stage,
        "delayed": delayed
    })

    return shipment_data


def train_delay_prediction_model():
    shipment_data = create_synthetic_shipment_data()

    shipment_data.to_csv(
        DATA_FILE,
        index=False
    )

    feature_columns = [
        "distance_km",
        "dispatch_delay_hours",
        "days_remaining",
        "documentation_complete",
        "vehicle_available",
        "priority",
        "transport_type",
        "current_stage"
    ]

    target_column = "delayed"

    features = shipment_data[
        feature_columns
    ]

    target = shipment_data[
        target_column
    ]

    numeric_features = [
        "distance_km",
        "dispatch_delay_hours",
        "days_remaining",
        "documentation_complete",
        "vehicle_available"
    ]

    categorical_features = [
        "priority",
        "transport_type",
        "current_stage"
    ]

    preprocessor = ColumnTransformer([
        (
            "numeric",
            "passthrough",
            numeric_features
        ),
        (
            "categorical",
            OneHotEncoder(
                handle_unknown="ignore"
            ),
            categorical_features
        )
    ])

    classifier = RandomForestClassifier(
        n_estimators=250,
        max_depth=12,
        min_samples_split=6,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=RANDOM_SEED,
        n_jobs=-1
    )

    model_pipeline = Pipeline([
        (
            "preprocessor",
            preprocessor
        ),
        (
            "classifier",
            classifier
        )
    ])

    (
        training_features,
        testing_features,
        training_target,
        testing_target
    ) = train_test_split(
        features,
        target,
        test_size=0.20,
        random_state=RANDOM_SEED,
        stratify=target
    )

    model_pipeline.fit(
        training_features,
        training_target
    )

    predicted_classes = model_pipeline.predict(
        testing_features
    )

    predicted_probabilities = (
        model_pipeline.predict_proba(
            testing_features
        )[:, 1]
    )

    metrics = {
        "accuracy": accuracy_score(
            testing_target,
            predicted_classes
        ),
        "precision": precision_score(
            testing_target,
            predicted_classes,
            zero_division=0
        ),
        "recall": recall_score(
            testing_target,
            predicted_classes,
            zero_division=0
        ),
        "f1_score": f1_score(
            testing_target,
            predicted_classes,
            zero_division=0
        ),
        "roc_auc": roc_auc_score(
            testing_target,
            predicted_probabilities
        )
    }

    model_package = {
        "model": model_pipeline,
        "feature_columns": feature_columns,
        "metrics": metrics,
        "training_rows": len(shipment_data),
        "data_source": "synthetic demonstration data"
    }

    joblib.dump(
        model_package,
        MODEL_FILE
    )

    print("")
    print("Shipment delay model trained successfully.")
    print(f"Training data saved to: {DATA_FILE}")
    print(f"Model saved to: {MODEL_FILE}")
    print("")
    print("Model evaluation:")
    print(
        f"Accuracy:  {metrics['accuracy']:.3f}"
    )
    print(
        f"Precision: {metrics['precision']:.3f}"
    )
    print(
        f"Recall:    {metrics['recall']:.3f}"
    )
    print(
        f"F1 Score:  {metrics['f1_score']:.3f}"
    )
    print(
        f"ROC AUC:   {metrics['roc_auc']:.3f}"
    )
    print("")


if __name__ == "__main__":
    train_delay_prediction_model()