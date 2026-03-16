"""
domain/events/__init__.py — Domain events.

Domain events are immutable records of something that happened inside the
domain.  They are named in the past tense (StudentEnrolled, not EnrollStudent)
because they describe a fact that is already true.

Events serve two purposes:
  1. Auditability — they provide a timestamped log of every state change.
  2. Decoupling   — the aggregate raises an event; the application service
                    publishes it; any subscriber can react without the aggregate
                    knowing who is listening.

All events use @dataclass(frozen=True) to enforce immutability.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events.  Every event records when it occurred."""
    occurred_on: datetime

@dataclass(frozen=True)
class StudentUpdated(DomainEvent):
    student_id: str
    name: str

@dataclass(frozen=True)
class StudentDeleted(DomainEvent):
    student_id: str
    name: str

@dataclass(frozen=True)
class InstructorUpdated(DomainEvent):
    instructor_id: str
    name: str

@dataclass(frozen=True)
class InstructorDeleted(DomainEvent):
    instructor_id: str
    name: str

@dataclass(frozen=True)
class OfferingUpdated(DomainEvent):
    offering_id: str
    course_code: str

@dataclass(frozen=True)
class OfferingDeleted(DomainEvent):
    offering_id: str
    course_code: str

# ---------------------------------------------------------------------------
# Enrollment events (raised by CourseOffering aggregate)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StudentEnrolled(DomainEvent):
    """Raised when a student is successfully added to a CourseOffering."""
    student_id  : str
    offering_id : str
    course_code : str


@dataclass(frozen=True)
class StudentDropped(DomainEvent):
    """Raised when a student voluntarily leaves a CourseOffering."""
    student_id  : str
    offering_id : str
    course_code : str


@dataclass(frozen=True)
class StudentWaitlisted(DomainEvent):
    """
    Raised when a student attempts to enroll but the course is full.
    The position field records where they sit in the queue (1 = next in line).
    """
    student_id  : str
    offering_id : str
    course_code : str
    position    : int


@dataclass(frozen=True)
class WaitlistPromoted(DomainEvent):
    """
    Raised when a seat opens up and the first student on the waitlist is
    automatically moved into the enrolled list.
    """
    student_id  : str
    offering_id : str
    course_code : str


# ---------------------------------------------------------------------------
# Course catalogue events (raised by the application service)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CourseCreated(DomainEvent):
    """Raised when a new Course is added to the catalogue."""
    course_code : str
    title       : str


@dataclass(frozen=True)
class CourseUpdated(DomainEvent):
    """Raised when a Course's title, credits, or prerequisites are changed."""
    course_code : str
    title       : str


@dataclass(frozen=True)
class CourseDeleted(DomainEvent):
    """Raised when a Course is permanently removed from the catalogue."""
    course_code : str
    title       : str
