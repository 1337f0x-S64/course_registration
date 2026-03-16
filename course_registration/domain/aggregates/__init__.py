"""
domain/aggregates/__init__.py — CourseOffering aggregate root.

An Aggregate is a cluster of domain objects treated as a single unit for
data changes.  The Aggregate Root is the only public entry point; all
mutations must go through it so invariants can never be bypassed.

CourseOffering is the aggregate root because it owns enrollment state (the
enrolled list and waitlist) and is responsible for enforcing every business
rule related to registration.

Invariants this aggregate enforces
-----------------------------------
1. enrolled count must never exceed capacity
2. a student must have completed all prerequisites before enrolling
3. a student may not enroll in two courses with overlapping schedules
   (this check is delegated to RegistrationService, which has the wider view)
4. a student's total semester credit load must not exceed MAX_CREDITS_PER_SEMESTER
5. enrollments and drops are only permitted while status is OPEN
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from course_registration.domain.entities      import Course, Instructor, Student
from course_registration.domain.value_objects import Semester, ScheduleSlot, OfferingStatus
from course_registration.domain.events        import (
    DomainEvent, StudentEnrolled, StudentDropped,
    StudentWaitlisted, WaitlistPromoted,
)


class EnrollmentError(Exception):
    """
    Raised when a business invariant blocks an enrollment or drop operation.
    The message is always human-readable so it can be shown directly to users.
    """


@dataclass
class CourseOffering:
    """
    Aggregate Root — a scheduled instance of a Course in a specific Semester.

    Public fields (set at construction):
        offering_id, course, instructor, semester, capacity, schedule, status

    Private fields (managed internally):
        _enrolled  — students currently enrolled
        _waitlist  — students queued when the course is full
        _events    — pending domain events, collected after each command

    The underscore prefix on private fields signals to all callers that they
    must NOT read or modify these directly.  Use the public properties and
    command methods instead.
    """

    offering_id : str
    course      : Course
    instructor  : Instructor
    semester    : Semester
    capacity    : int
    schedule    : List[ScheduleSlot] = field(default_factory=list)
    status      : OfferingStatus     = field(default=OfferingStatus.SCHEDULED)

    # Private state — never accessed directly from outside this class
    _enrolled : List[Student]     = field(default_factory=list, init=False, repr=False)
    _waitlist : List[Student]     = field(default_factory=list, init=False, repr=False)
    _events   : List[DomainEvent] = field(default_factory=list, init=False, repr=False)

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def enrolled(self) -> List[Student]:
        """Return a copy of the enrolled list so callers cannot mutate it."""
        return list(self._enrolled)

    @property
    def waitlist(self) -> List[Student]:
        """Return a copy of the waitlist so callers cannot mutate it."""
        return list(self._waitlist)

    @property
    def available_seats(self) -> int:
        """Remaining seats before the course is full."""
        return self.capacity - len(self._enrolled)

    def is_full(self) -> bool:
        """Return True when no more students can be directly enrolled."""
        return len(self._enrolled) >= self.capacity

    def is_student_enrolled(self, student: Student) -> bool:
        return student in self._enrolled

    def is_student_waitlisted(self, student: Student) -> bool:
        return student in self._waitlist

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def open_for_registration(self) -> None:
        """Transition SCHEDULED → OPEN, allowing enrollments to begin."""
        if self.status != OfferingStatus.SCHEDULED:
            raise EnrollmentError(f"Cannot open from status {self.status}.")
        self.status = OfferingStatus.OPEN

    def close_registration(self) -> None:
        """Transition OPEN → CLOSED, preventing any further enrollments."""
        if self.status != OfferingStatus.OPEN:
            raise EnrollmentError(f"Cannot close from status {self.status}.")
        self.status = OfferingStatus.CLOSED

    def complete(self) -> None:
        """Transition CLOSED → COMPLETED after the semester ends."""
        if self.status != OfferingStatus.CLOSED:
            raise EnrollmentError(f"Cannot complete from status {self.status}.")
        self.status = OfferingStatus.COMPLETED
        
    def update(self, capacity: int = None, schedule: list = None) -> None:
        if self.status != OfferingStatus.SCHEDULED:
            raise EnrollmentError(
                "Cannot edit an offering that has already been opened."
            )
        if capacity is not None:
            if capacity < 1:
                raise EnrollmentError("Capacity must be at least 1.")
            self.capacity = capacity
        if schedule is not None:
            self.schedule = schedule

    # ------------------------------------------------------------------
    # Commands — the only way to change enrollment state
    # ------------------------------------------------------------------

    def enroll_student(self, student: Student, current_credit_load: int = 0) -> None:
        """
        Attempt to enroll a student.  If the course is full, add them to the
        waitlist instead.  Raises EnrollmentError on any invariant violation.

        The caller (RegistrationService) is responsible for passing the
        student's current credit load so this aggregate can enforce the
        credit-limit rule without needing to query other aggregates itself.

        Invariant checks performed (in order):
          1. Status must be OPEN
          2. Student must not already be enrolled or waitlisted
          3. Student must have completed all prerequisites
          4. Adding this course must not exceed the credit limit
          5. If seats remain, enroll; otherwise, add to waitlist
        """
        # 1 — Registration window
        if self.status != OfferingStatus.OPEN:
            raise EnrollmentError(
                f"Registration for '{self.course}' is not open "
                f"(status: {self.status.value})."
            )

        # 2 — Duplicate check
        if self.is_student_enrolled(student):
            raise EnrollmentError(
                f"{student.name} is already enrolled in '{self.course}'."
            )
        if self.is_student_waitlisted(student):
            raise EnrollmentError(
                f"{student.name} is already on the waitlist for '{self.course}'."
            )

        # 3 — Prerequisites
        if not student.meets_prerequisites(self.course):
            missing = [
                str(p) for p in self.course.prerequisites
                if not student.has_completed(p)
            ]
            raise EnrollmentError(
                f"{student.name} has not completed prerequisites for "
                f"'{self.course.title}': {', '.join(missing)}."
            )

        # 4 — Credit load limit
        new_total = current_credit_load + self.course.credits
        if new_total > student.MAX_CREDITS_PER_SEMESTER:
            raise EnrollmentError(
                f"Enrolling in '{self.course.title}' would bring "
                f"{student.name} to {new_total} credits, exceeding the "
                f"{student.MAX_CREDITS_PER_SEMESTER}-credit limit."
            )

        # 5 — Capacity: enroll or waitlist
        if self.is_full():
            position = len(self._waitlist) + 1
            self._waitlist.append(student)
            self._events.append(StudentWaitlisted(
                occurred_on=datetime.now(),
                student_id=student.student_id,
                offering_id=self.offering_id,
                course_code=self.course.course_code,
                position=position,
            ))
        else:
            self._enrolled.append(student)
            self._events.append(StudentEnrolled(
                occurred_on=datetime.now(),
                student_id=student.student_id,
                offering_id=self.offering_id,
                course_code=self.course.course_code,
            ))

    def drop_student(self, student: Student) -> None:
        """
        Remove a student from the enrolled list.

        If the offering is still OPEN and students are on the waitlist,
        the first waitlisted student is automatically promoted to enrolled.
        This keeps capacity as full as possible without any extra orchestration.
        """
        if self.status not in (OfferingStatus.OPEN, OfferingStatus.CLOSED):
            raise EnrollmentError(
                f"Cannot drop from offering with status {self.status.value}."
            )
        if not self.is_student_enrolled(student):
            raise EnrollmentError(
                f"{student.name} is not enrolled in '{self.course.title}'."
            )

        self._enrolled.remove(student)
        self._events.append(StudentDropped(
            occurred_on=datetime.now(),
            student_id=student.student_id,
            offering_id=self.offering_id,
            course_code=self.course.course_code,
        ))

        # Auto-promote the next waitlisted student when registration is still open
        if self.status == OfferingStatus.OPEN and self._waitlist:
            promoted = self._waitlist.pop(0)
            self._enrolled.append(promoted)
            self._events.append(WaitlistPromoted(
                occurred_on=datetime.now(),
                student_id=promoted.student_id,
                offering_id=self.offering_id,
                course_code=self.course.course_code,
            ))

    # ------------------------------------------------------------------
    # Event collection
    # ------------------------------------------------------------------

    def collect_events(self) -> List[DomainEvent]:
        """
        Return all pending domain events and clear the internal list.

        Called by the Application Service immediately after saving the aggregate.
        This pattern (collect-then-publish) ensures events are only dispatched
        after the state change has been successfully persisted.
        """
        pending = list(self._events)
        self._events.clear()
        return pending

    def __str__(self) -> str:
        sched = ", ".join(str(s) for s in self.schedule) or "TBD"
        return (
            f"[{self.offering_id}] {self.course.title} | "
            f"{self.instructor.name} | {self.semester} | "
            f"{len(self._enrolled)}/{self.capacity} seats | "
            f"{sched} | {self.status.value}"
        )
