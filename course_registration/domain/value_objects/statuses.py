"""
statuses.py — Enumeration value objects for lifecycle states.

Enumerations are value objects: immutable, identity-less constants that
describe the valid states an entity or aggregate can occupy.  Using an
enum (instead of a bare string) means the compiler rejects typos and IDEs
provide autocomplete for every valid state.
"""

from enum import Enum


class RegistrationStatus(Enum):
    """
    Tracks where a Registration is in its lifecycle.

    PENDING   — created but not yet confirmed
    ACTIVE    — student is enrolled and attending
    DROPPED   — student voluntarily left the course
    COMPLETED — semester ended; student finished the course
    """
    PENDING   = "PENDING"
    ACTIVE    = "ACTIVE"
    DROPPED   = "DROPPED"
    COMPLETED = "COMPLETED"


class OfferingStatus(Enum):
    """
    Tracks the state of a CourseOffering through its lifecycle.

    SCHEDULED — created by a registrar; not yet open for enrollment
    OPEN      — students may enroll or drop
    CLOSED    — registration period has ended; no new enrollments
    COMPLETED — semester is over; final rosters are locked
    """
    SCHEDULED = "SCHEDULED"
    OPEN      = "OPEN"
    CLOSED    = "CLOSED"
    COMPLETED = "COMPLETED"
