import json
import os
from typing import Literal, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


load_dotenv()


class GeneratedTask(BaseModel):
    title: str = Field(
        description=(
            "A short and clear title for the task"
        )
    )

    description: str = Field(
        description=(
            "A clear description of what "
            "must be completed"
        )
    )

    priority: Literal[
        "low",
        "medium",
        "high"
    ] = Field(
        description="The priority of the task"
    )

    due_date: Optional[str] = Field(
        default=None,
        description=(
            "Due date in YYYY-MM-DD format, "
            "or null"
        )
    )


class ShipmentRiskAnalysis(BaseModel):
    executive_summary: str = Field(
        description=(
            "A concise executive summary "
            "of the shipment risk"
        )
    )

    operational_impact: str = Field(
        description=(
            "The possible impact on operations, "
            "customers, and delivery performance"
        )
    )

    urgency: Literal[
        "low",
        "medium",
        "high",
        "critical"
    ] = Field(
        description=(
            "The recommended urgency level"
        )
    )

    management_recommendation: str = Field(
        description=(
            "A clear recommendation for "
            "the operations manager"
        )
    )

    recommended_actions: list[str] = Field(
        description=(
            "A prioritized list of practical "
            "actions to reduce the risk"
        )
    )


def get_client():
    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY was not found "
            "in the .env file"
        )

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=30000
        )
    )


def generate_task(
    instruction: str
) -> GeneratedTask:
    client = get_client()

    prompt = f"""
You are an operations management assistant.

Convert the user's instruction into one clear task.

Rules:
- Create a short title.
- Create a useful description.
- Priority must be low, medium, or high.
- Use YYYY-MM-DD for the due date.
- If no due date is provided, return null.
- Do not invent a due date.

User instruction:
{instruction}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type=(
                "application/json"
            ),
            response_schema=GeneratedTask
        )
    )

    return GeneratedTask.model_validate_json(
        response.text
    )


def generate_report(
    tasks: list[dict]
) -> str:
    client = get_client()

    tasks_json = json.dumps(
        tasks,
        ensure_ascii=False,
        default=str
    )

    prompt = f"""
You are an operations management assistant.

Write a concise professional operations report
based only on the supplied tasks.

Include:
1. Executive summary
2. Completed tasks
3. Pending tasks
4. High-priority items
5. Recommended next actions

If there are no tasks, clearly state that
no tasks are available.

Tasks:
{tasks_json}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    return response.text


def generate_shipment_risk_analysis(
    shipment_data: dict
) -> ShipmentRiskAnalysis:
    client = get_client()

    shipment_json = json.dumps(
        shipment_data,
        ensure_ascii=False,
        default=str
    )

    prompt = f"""
You are a senior logistics and operations
risk analyst.

Analyze the supplied shipment prediction
and prepare a professional management assessment.

The machine-learning model has already calculated
the delay probability and risk level.

Your role is to:
- Explain the operational meaning of the result.
- Describe the possible impact on delivery,
  customers, and internal operations.
- Determine an appropriate urgency level.
- Provide a clear management recommendation.
- Produce a prioritized list of practical actions.

Rules:
- Use only the supplied shipment information.
- Do not invent costs, dates, customers,
  employees, or company policies.
- Do not change the machine-learning probability.
- Keep the response concise and professional.
- Write the response in English.
- Recommended actions must be realistic
  and directly related to the detected risks.

Shipment prediction:
{shipment_json}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type=(
                "application/json"
            ),
            response_schema=(
                ShipmentRiskAnalysis
            )
        )
    )

    return (
        ShipmentRiskAnalysis
        .model_validate_json(
            response.text
        )
    )