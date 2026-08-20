import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from .database import Base

class ChallengeStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    SOLVED = "SOLVED"
    FAILED = "FAILED"

class EventType(str, enum.Enum):
    PLAN = "PLAN"
    ACTION = "ACTION"
    OBSERVATION = "OBSERVATION"
    HYPOTHESIS = "HYPOTHESIS"
    SYSTEM = "SYSTEM"

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    
    users = relationship("User", back_populates="team")
    sessions = relationship("CtfSession", back_populates="team")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"))
    
    team = relationship("Team", back_populates="users")

class CtfSession(Base):
    __tablename__ = "ctf_sessions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    team = relationship("Team", back_populates="sessions")
    challenges = relationship("Challenge", back_populates="session")

class Challenge(Base):
    __tablename__ = "challenges"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("ctf_sessions.id"))
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True) # web, pwn, crypto, etc.
    target_urls = Column(JSON, default=list) # List of allowed URLs
    status = Column(Enum(ChallengeStatus), default=ChallengeStatus.QUEUED)
    assigned_model = Column(String, nullable=True)
    flag = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("CtfSession", back_populates="challenges")
    events = relationship("EventLog", back_populates="challenge")

class EventLog(Base):
    __tablename__ = "event_logs"
    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"))
    event_type = Column(Enum(EventType), nullable=False)
    content = Column(Text, nullable=False)
    tool_name = Column(String, nullable=True) # If it's a tool action
    created_at = Column(DateTime, default=datetime.utcnow)
    
    challenge = relationship("Challenge", back_populates="events")
