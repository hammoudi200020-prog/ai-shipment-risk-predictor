from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle
)
from sqlalchemy import text
from sqlalchemy.orm import Session

import ai_agent
import models
from database import Base, SessionLocal, engine


BASE_DIR = Path(__file__).resolve().parent


def ensure_task_columns():
    with engine.begin() as connection:
        result = connection.execute(
            text("PRAGMA table_info(tasks)")
        )

        existing_columns = {
            row[1]
            for row in result
        }

        if "department" not in existing_columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE tasks
                    ADD COLUMN department VARCHAR
                    DEFAULT 'General'
                    """
                )
            )

        if "assignee" not in existing_columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE tasks
                    ADD COLUMN assignee VARCHAR
                    DEFAULT 'Unassigned'
                    """
                )
            )


Base.metadata.create_all(bind=engine)
ensure_task_columns()


app = FastAPI(
    title="AI Operations Manager"
)


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    due_date: Optional[date] = None
    department: str = "General"
    assignee: str = "Unassigned"


class TaskStatusUpdate(BaseModel):
    status: str


class TaskAssignmentUpdate(BaseModel):
    department: str
    assignee: str


class EmployeeCreate(BaseModel):
    name: str
    email: str = ""
    department: str = "General"
    job_title: str = ""


class AgentRequest(BaseModel):
    instruction: str


def get_database():
    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()


@app.get(
    "/",
    include_in_schema=False
)
def home():
    return FileResponse(
        BASE_DIR / "index.html"
    )


@app.post("/tasks")
def create_task(
    task: TaskCreate,
    database: Session = Depends(get_database)
):
    new_task = models.Task(
        title=task.title,
        description=task.description,
        priority=task.priority,
        due_date=task.due_date,
        status="pending",
        department=task.department,
        assignee=task.assignee
    )

    database.add(new_task)
    database.commit()
    database.refresh(new_task)

    return new_task


@app.get("/tasks")
def get_tasks(
    database: Session = Depends(get_database)
):
    return database.query(
        models.Task
    ).all()


@app.patch("/tasks/{task_id}/status")
def update_task_status(
    task_id: int,
    update: TaskStatusUpdate,
    database: Session = Depends(get_database)
):
    task = database.query(
        models.Task
    ).filter(
        models.Task.id == task_id
    ).first()

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    task.status = update.status

    database.commit()
    database.refresh(task)

    return task


@app.patch("/tasks/{task_id}/assignment")
def update_task_assignment(
    task_id: int,
    update: TaskAssignmentUpdate,
    database: Session = Depends(get_database)
):
    task = database.query(
        models.Task
    ).filter(
        models.Task.id == task_id
    ).first()

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    task.department = update.department
    task.assignee = update.assignee

    database.commit()
    database.refresh(task)

    return task


@app.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    database: Session = Depends(get_database)
):
    task = database.query(
        models.Task
    ).filter(
        models.Task.id == task_id
    ).first()

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    database.delete(task)
    database.commit()

    return {
        "message": "Task deleted successfully"
    }


@app.post("/employees")
def create_employee(
    employee: EmployeeCreate,
    database: Session = Depends(get_database)
):
    if not employee.name.strip():
        raise HTTPException(
            status_code=400,
            detail="Employee name is required"
        )

    new_employee = models.Employee(
        name=employee.name.strip(),
        email=employee.email.strip(),
        department=employee.department,
        job_title=employee.job_title.strip()
    )

    database.add(new_employee)
    database.commit()
    database.refresh(new_employee)

    return new_employee


@app.get("/employees")
def get_employees(
    database: Session = Depends(get_database)
):
    return database.query(
        models.Employee
    ).order_by(
        models.Employee.name
    ).all()


@app.delete("/employees/{employee_id}")
def delete_employee(
    employee_id: int,
    database: Session = Depends(get_database)
):
    employee = database.query(
        models.Employee
    ).filter(
        models.Employee.id == employee_id
    ).first()

    if employee is None:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    database.delete(employee)
    database.commit()

    return {
        "message": "Employee deleted successfully"
    }


@app.get("/reports/summary")
def get_summary_report(
    database: Session = Depends(get_database)
):
    total_tasks = database.query(
        models.Task
    ).count()

    pending_tasks = database.query(
        models.Task
    ).filter(
        models.Task.status == "pending"
    ).count()

    completed_tasks = database.query(
        models.Task
    ).filter(
        models.Task.status == "completed"
    ).count()

    assigned_tasks = database.query(
        models.Task
    ).filter(
        models.Task.assignee != "Unassigned"
    ).count()

    total_employees = database.query(
        models.Employee
    ).count()

    return {
        "total_tasks": total_tasks,
        "pending_tasks": pending_tasks,
        "completed_tasks": completed_tasks,
        "assigned_tasks": assigned_tasks,
        "total_employees": total_employees
    }


@app.get("/reports/pdf")
def download_operations_report(
    database: Session = Depends(get_database)
):
    tasks = database.query(
        models.Task
    ).order_by(
        models.Task.id
    ).all()

    total_employees = database.query(
        models.Employee
    ).count()

    total_tasks = len(tasks)

    pending_tasks = sum(
        1
        for task in tasks
        if task.status == "pending"
    )

    in_progress_tasks = sum(
        1
        for task in tasks
        if task.status == "in_progress"
    )

    completed_tasks = sum(
        1
        for task in tasks
        if task.status == "completed"
    )

    assigned_tasks = sum(
        1
        for task in tasks
        if task.assignee != "Unassigned"
    )

    pdf_buffer = BytesIO()

    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="AI Operations Manager Report",
        author="AI Operations Manager"
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#0F172A"),
        alignment=TA_CENTER,
        spaceAfter=8
    )

    subtitle_style = ParagraphStyle(
        name="ReportSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748B"),
        alignment=TA_CENTER
    )

    section_style = ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1D4ED8"),
        spaceBefore=10,
        spaceAfter=8
    )

    normal_style = ParagraphStyle(
        name="TableText",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1F2937")
    )

    task_title_style = ParagraphStyle(
        name="TaskTitle",
        parent=normal_style,
        fontName="Helvetica",
        fontSize=8,
        leading=10
    )

    elements = []

    elements.append(
        Paragraph(
            "AI Operations Manager",
            title_style
        )
    )

    generated_time = datetime.now().strftime(
        "%Y-%m-%d %H:%M"
    )

    elements.append(
        Paragraph(
            f"Operations Report | Generated: {generated_time}",
            subtitle_style
        )
    )

    elements.append(
        Spacer(
            1,
            8 * mm
        )
    )

    elements.append(
        Paragraph(
            "Executive Summary",
            section_style
        )
    )

    summary_data = [
        [
            "Total Tasks",
            "Pending",
            "In Progress",
            "Completed",
            "Assigned",
            "Employees"
        ],
        [
            str(total_tasks),
            str(pending_tasks),
            str(in_progress_tasks),
            str(completed_tasks),
            str(assigned_tasks),
            str(total_employees)
        ]
    ]

    summary_table = Table(
        summary_data,
        colWidths=[
            35 * mm,
            35 * mm,
            35 * mm,
            35 * mm,
            35 * mm,
            35 * mm
        ]
    )

    summary_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#1D4ED8")
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
                colors.HexColor("#EFF6FF")
            ),
            (
                "TEXTCOLOR",
                (0, 1),
                (-1, 1),
                colors.HexColor("#0F172A")
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),
            (
                "FONTNAME",
                (0, 1),
                (-1, 1),
                "Helvetica-Bold"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                10
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, -1),
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
                0.5,
                colors.HexColor("#CBD5E1")
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                8
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                8
            )
        ])
    )

    elements.append(summary_table)

    elements.append(
        Spacer(
            1,
            7 * mm
        )
    )

    elements.append(
        Paragraph(
            "Task Details",
            section_style
        )
    )

    task_table_data = [[
        "ID",
        "Task",
        "Priority",
        "Department",
        "Assignee",
        "Due Date",
        "Status"
    ]]

    if tasks:
        for task in tasks:
            safe_title = escape(
                task.title or ""
            )

            safe_description = escape(
                task.description or ""
            )

            task_details = (
                f"<b>{safe_title}</b>"
            )

            if safe_description:
                task_details += (
                    f"<br/><font color='#64748B'>"
                    f"{safe_description}"
                    f"</font>"
                )

            task_table_data.append([
                str(task.id),
                Paragraph(
                    task_details,
                    task_title_style
                ),
                Paragraph(
                    escape(task.priority or "medium").title(),
                    normal_style
                ),
                Paragraph(
                    escape(task.department or "General"),
                    normal_style
                ),
                Paragraph(
                    escape(task.assignee or "Unassigned"),
                    normal_style
                ),
                str(task.due_date or "No due date"),
                Paragraph(
                    escape(
                        (task.status or "pending")
                        .replace("_", " ")
                        .title()
                    ),
                    normal_style
                )
            ])

    else:
        task_table_data.append([
            "",
            Paragraph(
                "No tasks are currently available.",
                normal_style
            ),
            "",
            "",
            "",
            "",
            ""
        ])

    task_table = Table(
        task_table_data,
        colWidths=[
            12 * mm,
            70 * mm,
            23 * mm,
            34 * mm,
            38 * mm,
            30 * mm,
            28 * mm
        ],
        repeatRows=1
    )

    task_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#0F172A")
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
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#CBD5E1")
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
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
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#F8FAFC")
                ]
            )
        ])
    )

    elements.append(task_table)

    elements.append(
        Spacer(
            1,
            8 * mm
        )
    )

    elements.append(
        Paragraph(
            "This report was generated automatically by "
            "the AI Operations Manager system.",
            subtitle_style
        )
    )

    document.build(elements)

    pdf_buffer.seek(0)

    file_name = (
        "operations_report_"
        f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{file_name}"'
        }
    )


@app.post("/agent/create-task")
def agent_create_task(
    request: AgentRequest,
    database: Session = Depends(get_database)
):
    try:
        generated_task = ai_agent.generate_task(
            request.instruction
        )

        parsed_due_date = None

        if generated_task.due_date:
            parsed_due_date = date.fromisoformat(
                generated_task.due_date
            )

        new_task = models.Task(
            title=generated_task.title,
            description=generated_task.description,
            priority=generated_task.priority,
            due_date=parsed_due_date,
            status="pending",
            department="General",
            assignee="Unassigned"
        )

        database.add(new_task)
        database.commit()
        database.refresh(new_task)

        return {
            "message": "Task created by AI successfully",
            "task": new_task
        }

    except Exception as error:
        database.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"AI service error: {str(error)}"
        )


@app.get("/agent/report")
def agent_generate_report(
    database: Session = Depends(get_database)
):
    try:
        tasks = database.query(
            models.Task
        ).all()

        task_data = []

        for task in tasks:
            task_data.append({
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "due_date": task.due_date,
                "status": task.status,
                "department": task.department,
                "assignee": task.assignee
            })

        report = ai_agent.generate_report(
            task_data
        )

        return {
            "report": report
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"AI service error: {str(error)}"
        )