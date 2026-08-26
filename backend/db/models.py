"""SQLAlchemy models for Argus (teams, users, sessions, challenges, events).

Typed with SQLAlchemy 2.0 ``Mapped``/``mapped_column`` annotations.
"""

import enum
from datetime import datetime
from typing import List, Optional

# pi-lens-ignore: python-hallucinated-import
from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ChallengeStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    SOLVED = "SOLVED"
    FAILED = "FAILED"
    # Agent has proposed a flag and is paused, awaiting human verification.
    FLAG_PROPOSED = "FLAG_PROPOSED"


class EventType(str, enum.Enum):
    PLAN = "PLAN"
    ACTION = "ACTION"
    OBSERVATION = "OBSERVATION"
    HYPOTHESIS = "HYPOTHESIS"
    SYSTEM = "SYSTEM"


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)

    users: Mapped[List["User"]] = relationship(back_populates="team")
    sessions: Mapped[List["CtfSession"]] = relationship(back_populates="team")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="user")
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"))

    team: Mapped[Optional["Team"]] = relationship(back_populates="users")


class CtfSession(Base):
    __tablename__ = "ctf_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"))
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    team: Mapped[Optional["Team"]] = relationship(back_populates="sessions")
    challenges: Mapped[List["Challenge"]] = relationship(back_populates="session")


class Challenge(Base):
    __tablename__ = "challenges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ctf_sessions.id"))
    title: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String)  # web, pwn, crypto, etc.
    target_urls: Mapped[Optional[list]] = mapped_column(
        JSON, default=list
    )  # List of allowed URLs
    status: Mapped[Optional[ChallengeStatus]] = mapped_column(
        Enum(ChallengeStatus), default=ChallengeStatus.QUEUED
    )
    assigned_model: Mapped[Optional[str]] = mapped_column(String)
    flag: Mapped[Optional[str]] = mapped_column(String)
    proposed_flag: Mapped[Optional[str]] = mapped_column(
        String
    )  # last flag the agent proposed
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    session: Mapped[Optional["CtfSession"]] = relationship(back_populates="challenges")
    events: Mapped[List["EventLog"]] = relationship(back_populates="challenge")


class EventLog(Base):
    __tablename__ = "event_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    challenge_id: Mapped[Optional[int]] = mapped_column(ForeignKey("challenges.id"))
    event_type: Mapped[EventType] = mapped_column(Enum(EventType))
    content: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[Optional[str]] = mapped_column(String)  # If it's a tool action
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    challenge: Mapped[Optional["Challenge"]] = relationship(back_populates="events")
