"""
application/dtos/__init__.py — Data Transfer Objects.

A DTO (Data Transfer Object) is a plain, immutable data container that
carries information OUT of the application layer to any presentation layer
(CLI, GUI, REST API, etc.).

Why DTOs instead of returning raw domain objects?
-------------------------------------------------
1. Separation of concerns — domain objects carry business logic and methods.
   Presentation layers should only read data, never call domain methods on
   objects they received from a query.

2. Stable API contract — the domain model can be refactored internally without
   breaking the GUI or CLI, as long as the DTO fields stay the same.

3. GUI-friendliness — widget libraries (tkinter, PyQt, wxPython) can bind
   directly to simple fields on a frozen dataclass.

4. Future-proofing — converting a DTO to JSON for a REST response or to a
   database row is straightforward; doing the same with a domain object
   (which may have circular references and private state) is not.

All DTOs use @dataclass(frozen=True) to prevent accidental mutation.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class CourseDTO:
    """A read-only snapshot of a Course entity."""
    course_code   : str
    title         : str
    credits       : int
    prerequisites : List[str]       # course_codes only — no domain objects


@dataclass(frozen=True)
class InstructorDTO:
    """A read-only snapshot of an Instructor entity."""
    instructor_id : str
    name          : str
    department    : str


@dataclass(frozen=True)
class StudentDTO:
    """A read-only snapshot of a Student entity."""
    student_id        : str
    name              : str
    program           : str
    completed_courses : List[str]   # course_codes only


@dataclass(frozen=True)
class ScheduleSlotDTO:
    """A read-only snapshot of a ScheduleSlot value object."""
    day        : str
    start_time : str
    end_time   : str

    def __str__(self) -> str:
        return f"{self.day} {self.start_time}-{self.end_time}"


@dataclass(frozen=True)
class OfferingDTO:
    """
    A read-only snapshot of a CourseOffering aggregate.

    Computed properties (available_seats, is_full) are included for
    convenience so the GUI does not need to derive them from raw counts.
    """
    offering_id    : str
    course         : CourseDTO
    instructor     : InstructorDTO
    semester_label : str            # e.g. "Spring 2026"
    capacity       : int
    enrolled_count : int
    waitlist_count : int
    status         : str            # e.g. "OPEN", "CLOSED"
    schedule       : List[ScheduleSlotDTO]

    @property
    def available_seats(self) -> int:
        return self.capacity - self.enrolled_count

    @property
    def is_full(self) -> bool:
        return self.enrolled_count >= self.capacity


@dataclass(frozen=True)
class EnrollmentResultDTO:
    """
    Returned by enroll_student() and drop_student() on success.

    success    : always True when this type is returned (errors use ErrorDTO)
    waitlisted : True if the student was queued rather than directly enrolled
    message    : plain-English summary — CLI prints it; GUI shows it in a dialog
    offering   : fresh OfferingDTO so the GUI can update its view in one round-trip
    """
    success    : bool
    waitlisted : bool
    message    : str
    offering   : OfferingDTO


@dataclass(frozen=True)
class CourseManagementResultDTO:
    """
    Returned by add_course(), update_course(), and delete_course() on success.

    success : always True (errors use ErrorDTO)
    action  : one of "created", "updated", "deleted" — lets the GUI update
              its view correctly (e.g. remove a row vs refresh a row)
    message : plain-English summary for display
    course  : updated CourseDTO snapshot, or None when the course was deleted
    """
    success : bool
    action  : str           # "created" | "updated" | "deleted"
    message : str
    course  : CourseDTO     # None when action == "deleted"


@dataclass(frozen=True)
class ErrorDTO:
    """
    Returned instead of raising an exception at the application boundary.

    Returning an error value (rather than throwing) means:
    - The CLI can print it without a try/except block.
    - The GUI can inspect the code field and react accordingly
      (highlight a field, open a specific dialog, etc.).

    code : machine-readable identifier for the GUI to branch on
           e.g. "NOT_FOUND", "ENROLLMENT_RULE_VIOLATION", "INVALID_STATE",
                "COURSE_IN_USE", "DUPLICATE_COURSE_CODE", "VALIDATION_ERROR"
    """
    message : str
    code    : str = "GENERAL_ERROR"
