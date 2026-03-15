"""
domain/value_objects/__init__.py

Re-exports all value objects so the rest of the codebase can use a single
import path:

    from course_registration.domain.value_objects import Semester, ScheduleSlot

Each class lives in its own module for readability; this file stitches them
together into a single public surface.
"""

from .semester      import Semester
from .schedule_slot import ScheduleSlot
from .statuses      import RegistrationStatus, OfferingStatus

__all__ = ["Semester", "ScheduleSlot", "RegistrationStatus", "OfferingStatus"]
