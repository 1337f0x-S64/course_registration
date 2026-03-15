"""
domain/services/__init__.py — RegistrationService domain service.

A Domain Service contains business logic that does not naturally belong to
a single Entity or Aggregate.

RegistrationService handles the schedule-overlap check.  This logic requires
inspecting all of a student's current enrollments across multiple
CourseOffering aggregates, so it cannot live inside any one of them.

The service is stateless: it holds no data of its own and is safe to
instantiate once and reuse across all use cases.
"""

from __future__ import annotations
from typing import List

from course_registration.domain.entities      import Student
from course_registration.domain.aggregates    import CourseOffering, EnrollmentError
from course_registration.domain.value_objects import ScheduleSlot


class RegistrationService:
    """
    Orchestrates cross-aggregate enrollment rules.

    Responsibilities
    ----------------
    - Detect schedule conflicts across all of a student's active offerings
    - Calculate the student's current credit load for the semester
    - Coordinate the full enroll and drop workflow by delegating to the
      aggregate root after completing its own cross-cutting checks
    """

    def total_credits_for_student(
        self,
        student          : Student,
        active_offerings : List[CourseOffering],
    ) -> int:
        """
        Sum the credits of every offering the student is currently enrolled in.

        The caller passes all offerings for the semester so this service does
        not need to access a repository — keeping it decoupled from persistence.
        """
        return sum(
            o.course.credits
            for o in active_offerings
            if o.is_student_enrolled(student)
        )

    def has_schedule_conflict(
        self,
        student          : Student,
        target_offering  : CourseOffering,
        active_offerings : List[CourseOffering],
    ) -> bool:
        """
        Return True if any slot in target_offering overlaps with a slot from
        an offering the student is already enrolled in.
        """
        # Gather every time slot the student is already committed to
        student_slots: List[ScheduleSlot] = []
        for o in active_offerings:
            if o.is_student_enrolled(student):
                student_slots.extend(o.schedule)

        # Check each new slot against every existing slot
        for existing in student_slots:
            for new in target_offering.schedule:
                if existing.overlaps_with(new):
                    return True
        return False

    def enroll(
        self,
        student          : Student,
        target_offering  : CourseOffering,
        active_offerings : List[CourseOffering],
    ) -> None:
        """
        Full enrollment workflow.

        Steps:
          1. Check for schedule conflicts (Domain Service responsibility)
          2. Calculate the student's current credit load
          3. Delegate to the Aggregate Root for all remaining invariant checks

        Raises EnrollmentError with a plain-English message on any violation.
        """
        if self.has_schedule_conflict(student, target_offering, active_offerings):
            slots = ", ".join(str(s) for s in target_offering.schedule)
            raise EnrollmentError(
                f"{student.name} has a schedule conflict with "
                f"'{target_offering.course.title}' ({slots})."
            )

        current_credits = self.total_credits_for_student(student, active_offerings)
        target_offering.enroll_student(student, current_credit_load=current_credits)

    def drop(self, student: Student, target_offering: CourseOffering) -> None:
        """
        Drop a student from an offering.
        The Aggregate Root handles waitlist promotion automatically.
        """
        target_offering.drop_student(student)
