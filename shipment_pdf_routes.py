import json
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle
)
from sqlalchemy.orm import Session

import models
from shipment_routes import get_database


router = APIRouter(
    prefix="/shipments",
    tags=["Shipment PDF Reports"]
)


def parse_list(value):
    if isinstance(value, list):
        return value

    if not value:
        return []

    try:
        result = json.loads(value)

        if isinstance(result, list):
            return result

        return []

    except (
        json.JSONDecodeError,
        TypeError
    ):
        return []


@router.get("/report/pdf")
def download_shipment_risk_report(
    database: Session = Depends(
        get_database
    )
):
    shipments = (
        database.query(models.Shipment)
        .order_by(
            models.Shipment
            .delay_probability
            .desc()
        )
        .all()
    )

    total = len(shipments)

    high = sum(
        shipment.risk_level == "High"
        for shipment in shipments
    )

    medium = sum(
        shipment.risk_level == "Medium"
        for shipment in shipments
    )

    low = sum(
        shipment.risk_level == "Low"
        for shipment in shipments
    )

    delayed = sum(
        shipment.actual_status == "delayed"
        for shipment in shipments
    )

    probabilities = [
        float(
            shipment.delay_probability or 0
        )
        for shipment in shipments
    ]

    if total:
        average = (
            sum(probabilities) / total
        )
    else:
        average = 0

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="AI Shipment Risk Report",
        author="AI Operations Manager"
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=27,
        alignment=TA_CENTER,
        textColor=colors.HexColor(
            "#102A43"
        ),
        spaceAfter=8
    )

    subtitle_style = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor(
            "#64748B"
        ),
        spaceAfter=15
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor(
            "#102A43"
        ),
        spaceBefore=8,
        spaceAfter=9
    )

    normal_style = ParagraphStyle(
        "CustomNormal",
        parent=styles["Normal"],
        fontSize=8,
        leading=12,
        textColor=colors.HexColor(
            "#334E68"
        )
    )

    warning_style = ParagraphStyle(
        "Warning",
        parent=normal_style,
        textColor=colors.HexColor(
            "#7C2D12"
        ),
        backColor=colors.HexColor(
            "#FFF7ED"
        ),
        borderColor=colors.HexColor(
            "#FDBA74"
        ),
        borderWidth=1,
        borderPadding=7,
        spaceAfter=12
    )

    story = [
        Paragraph(
            "AI Shipment Delay &amp; Risk Report",
            title_style
        ),
        Paragraph(
            (
                "Generated on "
                + datetime.now().strftime(
                    "%Y-%m-%d %H:%M"
                )
            ),
            subtitle_style
        ),
        Paragraph(
            (
                "<b>Portfolio demonstration:</b> "
                "The prediction model uses synthetic "
                "training data. Production use requires "
                "validation with real company shipment "
                "data."
            ),
            warning_style
        ),
        Paragraph(
            "Executive Summary",
            heading_style
        )
    ]

    summary_data = [
        [
            "Total Shipments",
            "High Risk",
            "Medium Risk",
            "Low Risk",
            "Average Risk",
            "Actually Delayed"
        ],
        [
            str(total),
            str(high),
            str(medium),
            str(low),
            f"{average:.1f}%",
            str(delayed)
        ]
    ]

    summary_table = Table(
        summary_data,
        colWidths=[
            42 * mm,
            38 * mm,
            38 * mm,
            38 * mm,
            42 * mm,
            42 * mm
        ]
    )

    summary_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#102A43"
                    )
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),
                (
                    "BACKGROUND",
                    (0, 1),
                    (-1, 1),
                    colors.HexColor(
                        "#F1F5F9"
                    )
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, -1),
                    "Helvetica-Bold"
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    9
                ),
                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor(
                        "#CBD5E1"
                    )
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    9
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    9
                )
            ]
        )
    )

    story.extend(
        [
            summary_table,
            Spacer(
                1,
                8 * mm
            )
        ]
    )

    story.append(
        Paragraph(
            "Shipment Risk Register",
            heading_style
        )
    )

    if shipments:
        table_data = [
            [
                "Shipment",
                "Route",
                "Distance",
                "Delay",
                "Days Left",
                "Priority",
                "Probability",
                "Risk",
                "Prediction",
                "Actual"
            ]
        ]

        for shipment in shipments:
            probability = float(
                shipment.delay_probability or 0
            )

            route = (
                shipment.origin
                + " to "
                + shipment.destination
            )

            distance = (
                str(shipment.distance_km)
                + " km"
            )

            delay = (
                str(
                    shipment
                    .dispatch_delay_hours
                )
                + " hrs"
            )

            table_data.append(
                [
                    Paragraph(
                        str(
                            shipment
                            .shipment_number
                        ),
                        normal_style
                    ),
                    Paragraph(
                        route,
                        normal_style
                    ),
                    Paragraph(
                        distance,
                        normal_style
                    ),
                    Paragraph(
                        delay,
                        normal_style
                    ),
                    Paragraph(
                        str(
                            shipment
                            .days_remaining
                        ),
                        normal_style
                    ),
                    Paragraph(
                        str(
                            shipment.priority
                        ),
                        normal_style
                    ),
                    Paragraph(
                        f"{probability:.1f}%",
                        normal_style
                    ),
                    Paragraph(
                        str(
                            shipment.risk_level
                        ),
                        normal_style
                    ),
                    Paragraph(
                        str(
                            shipment.prediction
                        ),
                        normal_style
                    ),
                    Paragraph(
                        str(
                            shipment.actual_status
                        ),
                        normal_style
                    )
                ]
            )

        shipment_table = Table(
            table_data,
            repeatRows=1,
            colWidths=[
                25 * mm,
                44 * mm,
                22 * mm,
                20 * mm,
                20 * mm,
                22 * mm,
                25 * mm,
                21 * mm,
                32 * mm,
                24 * mm
            ]
        )

        shipment_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor(
                            "#155E75"
                        )
                    ),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        colors.white
                    ),
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, 0),
                        "Helvetica-Bold"
                    ),
                    (
                        "FONTSIZE",
                        (0, 0),
                        (-1, 0),
                        8
                    ),
                    (
                        "ALIGN",
                        (0, 0),
                        (-1, 0),
                        "CENTER"
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "MIDDLE"
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.35,
                        colors.HexColor(
                            "#CBD5E1"
                        )
                    ),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [
                            colors.white,
                            colors.HexColor(
                                "#F8FAFC"
                            )
                        ]
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        6
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        6
                    )
                ]
            )
        )

        story.append(
            shipment_table
        )

    else:
        story.append(
            Paragraph(
                (
                    "No shipment records "
                    "are available."
                ),
                normal_style
            )
        )

    high_risk_shipments = [
        shipment
        for shipment in shipments
        if shipment.risk_level == "High"
    ]

    if high_risk_shipments:
        story.append(
            Spacer(
                1,
                8 * mm
            )
        )

        story.append(
            Paragraph(
                "High-Risk Action Plan",
                heading_style
            )
        )

        for shipment in high_risk_shipments:
            probability = float(
                shipment.delay_probability or 0
            )

            shipment_title = (
                str(
                    shipment.shipment_number
                )
                + " - "
                + shipment.origin
                + " to "
                + shipment.destination
                + f" - {probability:.1f}% risk"
            )

            story.append(
                Paragraph(
                    (
                        "<b>"
                        + shipment_title
                        + "</b>"
                    ),
                    normal_style
                )
            )

            risk_factors = parse_list(
                shipment.risk_factors
            )

            actions = parse_list(
                shipment.recommended_actions
            )

            story.append(
                Paragraph(
                    "<b>Risk factors:</b>",
                    normal_style
                )
            )

            if risk_factors:
                for factor in risk_factors:
                    story.append(
                        Paragraph(
                            "- " + str(factor),
                            normal_style
                        )
                    )
            else:
                story.append(
                    Paragraph(
                        (
                            "- No risk factors "
                            "recorded."
                        ),
                        normal_style
                    )
                )

            story.append(
                Paragraph(
                    (
                        "<b>Recommended "
                        "actions:</b>"
                    ),
                    normal_style
                )
            )

            if actions:
                for number, action in enumerate(
                    actions,
                    start=1
                ):
                    action_text = (
                        str(number)
                        + ". "
                        + str(action)
                    )

                    story.append(
                        Paragraph(
                            action_text,
                            normal_style
                        )
                    )
            else:
                story.append(
                    Paragraph(
                        (
                            "- No actions "
                            "recorded."
                        ),
                        normal_style
                    )
                )

            story.append(
                Spacer(
                    1,
                    5 * mm
                )
            )

    document.build(story)
    buffer.seek(0)

    file_name = (
        "shipment_risk_report_"
        + datetime.now().strftime(
            "%Y%m%d_%H%M"
        )
        + ".pdf"
    )

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                (
                    "attachment; "
                    f'filename="{file_name}"'
                )
        }
    )