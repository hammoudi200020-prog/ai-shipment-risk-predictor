from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text
)

from database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    title = Column(
        String,
        nullable=False
    )

    description = Column(
        String,
        default=""
    )

    priority = Column(
        String,
        default="medium"
    )

    due_date = Column(
        Date,
        nullable=True
    )

    status = Column(
        String,
        default="pending"
    )

    department = Column(
        String,
        default="General"
    )

    assignee = Column(
        String,
        default="Unassigned"
    )


class Employee(Base):
    __tablename__ = "employees"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String,
        nullable=False
    )

    email = Column(
        String,
        default=""
    )

    department = Column(
        String,
        default="General"
    )

    job_title = Column(
        String,
        default=""
    )


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    shipment_number = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    origin = Column(
        String,
        nullable=False
    )

    destination = Column(
        String,
        nullable=False
    )

    distance_km = Column(
        Float,
        nullable=False
    )

    dispatch_delay_hours = Column(
        Integer,
        default=0
    )

    days_remaining = Column(
        Integer,
        nullable=False
    )

    documentation_complete = Column(
        Boolean,
        default=True
    )

    vehicle_available = Column(
        Boolean,
        default=True
    )

    priority = Column(
        String,
        default="medium"
    )

    transport_type = Column(
        String,
        default="road"
    )

    current_stage = Column(
        String,
        default="processing"
    )

    delay_probability = Column(
        Float,
        nullable=True
    )

    risk_level = Column(
        String,
        default="Not Predicted"
    )

    prediction = Column(
        String,
        default="Not Predicted"
    )

    risk_factors = Column(
        Text,
        default="[]"
    )

    recommended_actions = Column(
        Text,
        default="[]"
    )

    actual_status = Column(
        String,
        default="unknown"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )