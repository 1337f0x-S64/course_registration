"""
application/services/__init__.py — RegistrationAppService.

The Application Service is the entry point for every use case.  It acts as
a thin orchestration layer that:
  1. Loads entities and aggregates from repositories
  2. Calls domain logic (domain services and aggregate commands)
  3. Persists the updated aggregates
  4. Publishes domain events via EventPublisher

It contains NO business logic of its own.  All rules live in the domain.

GUI-readiness
-------------
- Every method returns a DTO or ErrorDTO — no raw domain objects or strings.
- Errors are returned as ErrorDTO values, not raised exceptions.
- All print() calls have been removed; events are dispatched via EventPublisher.
- EventPublisher is constructor-injected so any presentation layer can supply
  its own handlers without touching this class.

Course management methods
-------------------------
add_course()     — already existed; now also fires CourseCreated event
update_course()  — NEW: change title, credits, and/or prerequisites
delete_course()  — NEW: remove a course; blocked if active offerings exist
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Union

from course_registration.domain.entities      import Course, Instructor, Student
from course_registration.domain.aggregates    import CourseOffering, EnrollmentError
from course_registration.domain.value_objects import Semester, ScheduleSlot
from course_registration.domain.services      import RegistrationService
from course_registration.domain.repositories  import (
    StudentRepository, CourseRepository,
    InstructorRepository, CourseOfferingRepository,
)
from course_registration.domain.events import (
    CourseCreated, CourseUpdated, CourseDeleted,
)
from course_registration.application.dtos import (
    CourseDTO, InstructorDTO, StudentDTO,
    ScheduleSlotDTO, OfferingDTO,
    EnrollmentResultDTO, CourseManagementResultDTO, ErrorDTO,
)
from course_registration.application.services.event_publisher import EventPublisher


# ---------------------------------------------------------------------------
# DTO assemblers — private helpers
# ---------------------------------------------------------------------------
# These translate domain objects into DTOs.  They live in the application
# layer (not the domain) because the domain must never know about DTOs.

def _course_dto(c: Course) -> CourseDTO:
    return CourseDTO(
        course_code=c.course_code, title=c.title, credits=c.credits,
        prerequisites=[p.course_code for p in c.prerequisites],
    )

def _instructor_dto(i: Instructor) -> InstructorDTO:
    return InstructorDTO(instructor_id=i.instructor_id, name=i.name, department=i.department)

def _student_dto(s: Student) -> StudentDTO:
    return StudentDTO(
        student_id=s.student_id, name=s.name, program=s.program,
        completed_courses=[c.course_code for c in s.completed_courses],
    )

def _offering_dto(o: CourseOffering) -> OfferingDTO:
    return OfferingDTO(
        offering_id=o.offering_id,
        course=_course_dto(o.course),
        instructor=_instructor_dto(o.instructor),
        semester_label=str(o.semester),
        capacity=o.capacity,
        enrolled_count=len(o.enrolled),
        waitlist_count=len(o.waitlist),
        status=o.status.value,
        schedule=[
            ScheduleSlotDTO(day=s.day, start_time=s.start_time, end_time=s.end_time)
            for s in o.schedule
        ],
    )


# ---------------------------------------------------------------------------
# Application Service
# ---------------------------------------------------------------------------

class RegistrationAppService:
    """
    Orchestrates all system use cases.

    All dependencies are injected through the constructor.  This means:
    - Any presentation layer (CLI, GUI) calls bootstrap.create_app() to
      receive a fully wired instance without knowing how it was assembled.
    - Tests can inject fakes for any dependency without modifying this class.
    """

    def __init__(
        self,
        student_repo    : StudentRepository,
        course_repo     : CourseRepository,
        instructor_repo : InstructorRepository,
        offering_repo   : CourseOfferingRepository,
        event_publisher : EventPublisher,
    ) -> None:
        self._students    = student_repo
        self._courses     = course_repo
        self._instructors = instructor_repo
        self._offerings   = offering_repo
        self._publisher   = event_publisher
        self._reg_service = RegistrationService()

    # ------------------------------------------------------------------
    # Course management — add, update, delete
    # ------------------------------------------------------------------

    def add_course(
        self,
        course_code        : str,
        title              : str,
        credits            : int,
        prerequisite_codes : List[str] = None,
    ) -> Union[CourseManagementResultDTO, ErrorDTO]:
        """
        Add a new Course to the catalogue.

        Returns CourseManagementResultDTO(action="created") on success.
        Returns ErrorDTO with code DUPLICATE_COURSE_CODE if the code already exists.
        """
        # Guard: course codes must be unique
        if self._courses.find_by_code(course_code):
            return ErrorDTO(
                f"A course with code '{course_code}' already exists.",
                "DUPLICATE_COURSE_CODE",
            )

        course = Course(course_code=course_code, title=title, credits=credits)

        # Resolve prerequisites — skip codes that don't exist yet (best-effort)
        for code in (prerequisite_codes or []):
            prereq = self._courses.find_by_code(code)
            if prereq:
                course.add_prerequisite(prereq)

        self._courses.save(course)
        self._publisher.publish(CourseCreated(
            occurred_on=datetime.now(), course_code=course_code, title=title
        ))

        return CourseManagementResultDTO(
            success=True, action="created",
            message=f"Course '{course_code} - {title}' added to the catalogue.",
            course=_course_dto(course),
        )

    def update_course(
        self,
        course_code        : str,
        new_title          : str = None,
        new_credits        : int = None,
        new_prereq_codes   : List[str] = None,
    ) -> Union[CourseManagementResultDTO, ErrorDTO]:
        """
        Update an existing Course's title, credit value, and/or prerequisites.

        Parameters
        ----------
        course_code
            The code identifying the course to update.
        new_title
            Pass a string to change the title, or None to leave it unchanged.
        new_credits
            Pass an integer to change the credits, or None to leave unchanged.
        new_prereq_codes
            Pass a list of course codes to replace the full prerequisite list.
            Pass [] to clear all prerequisites.
            Pass None to leave prerequisites unchanged.

        Business rules enforced
        -----------------------
        - A course cannot be its own prerequisite.
        - Every prerequisite code must refer to an existing course.
        - Credits must be a positive integer.
        - Title cannot be blank.

        Returns CourseManagementResultDTO(action="updated") on success.
        Returns ErrorDTO on validation failure or if the course is not found.
        """
        course = self._get_course_domain(course_code)
        if isinstance(course, ErrorDTO):
            return course

        # Build a lookup dict needed by Course.update() to resolve prereq codes
        all_courses = {c.course_code: c for c in self._courses.find_all()}

        try:
            course.update(
                title=new_title,
                credits=new_credits,
                new_prereq_codes=new_prereq_codes,
                all_courses=all_courses,
            )
        except ValueError as e:
            return ErrorDTO(str(e), "VALIDATION_ERROR")

        self._courses.save(course)
        self._publisher.publish(CourseUpdated(
            occurred_on=datetime.now(),
            course_code=course.course_code,
            title=course.title,
        ))

        return CourseManagementResultDTO(
            success=True, action="updated",
            message=f"Course '{course_code}' updated successfully.",
            course=_course_dto(course),
        )

    def delete_course(
        self, course_code: str
    ) -> Union[CourseManagementResultDTO, ErrorDTO]:
        """
        Permanently delete a Course from the catalogue.

        Safety checks performed before deletion
        ----------------------------------------
        1. The course must exist.
        2. No CourseOffering (in any status) may still reference this course.
           Deleting a course that has offerings would leave those offerings
           referencing a non-existent catalogue entry.
        3. The course must not appear in any other course's prerequisite list.
           Deleting it would silently break those prerequisite chains.

        If any check fails, an ErrorDTO with code COURSE_IN_USE is returned
        and the course is NOT deleted.

        Returns CourseManagementResultDTO(action="deleted", course=None) on success.
        """
        course = self._get_course_domain(course_code)
        if isinstance(course, ErrorDTO):
            return course

        # Check 1 — active or historical offerings
        offerings_using = self._offerings.find_by_course(course_code)
        if offerings_using:
            offering_ids = ", ".join(o.offering_id for o in offerings_using)
            return ErrorDTO(
                f"Cannot delete '{course_code}': it is referenced by "
                f"offering(s) {offering_ids}. Remove those offerings first.",
                "COURSE_IN_USE",
            )

        # Check 2 — other courses that list this as a prerequisite
        dependents = [
            c.course_code for c in self._courses.find_all()
            if any(p.course_code == course_code for p in c.prerequisites)
        ]
        if dependents:
            return ErrorDTO(
                f"Cannot delete '{course_code}': it is a prerequisite for "
                f"{', '.join(dependents)}. Remove those dependencies first.",
                "COURSE_IN_USE",
            )

        title = course.title  # capture before deletion for the event/message
        self._courses.delete(course_code)
        self._publisher.publish(CourseDeleted(
            occurred_on=datetime.now(), course_code=course_code, title=title
        ))

        return CourseManagementResultDTO(
            success=True, action="deleted",
            message=f"Course '{course_code} - {title}' deleted from the catalogue.",
            course=None,
        )

    # ------------------------------------------------------------------
    # Other setup commands
    # ------------------------------------------------------------------

    def add_student(self, student_id: str, name: str, program: str) -> StudentDTO:
        """Create and persist a new Student; return its DTO."""
        student = Student(student_id=student_id, name=name, program=program)
        self._students.save(student)
        return _student_dto(student)

    def add_instructor(self, instructor_id: str, name: str, department: str) -> InstructorDTO:
        """Create and persist a new Instructor; return its DTO."""
        instructor = Instructor(instructor_id=instructor_id, name=name, department=department)
        self._instructors.save(instructor)
        return _instructor_dto(instructor)

    def create_offering(
        self,
        offering_id   : str,
        course_code   : str,
        instructor_id : str,
        semester      : Semester,
        capacity      : int,
        schedule      : List[ScheduleSlot] = None,
    ) -> Union[OfferingDTO, ErrorDTO]:
        """Create and persist a new CourseOffering; return its DTO or an ErrorDTO."""
        course     = self._courses.find_by_code(course_code)
        instructor = self._instructors.find_by_id(instructor_id)
        if not course:
            return ErrorDTO(f"Course '{course_code}' not found.", "NOT_FOUND")
        if not instructor:
            return ErrorDTO(f"Instructor '{instructor_id}' not found.", "NOT_FOUND")
        offering = CourseOffering(
            offering_id=offering_id, course=course, instructor=instructor,
            semester=semester, capacity=capacity, schedule=schedule or [],
        )
        self._offerings.save(offering)
        return _offering_dto(offering)

    def open_offering(self, offering_id: str) -> Union[OfferingDTO, ErrorDTO]:
        """Transition a CourseOffering from SCHEDULED to OPEN."""
        offering = self._get_offering_domain(offering_id)
        if isinstance(offering, ErrorDTO):
            return offering
        try:
            offering.open_for_registration()
            self._offerings.save(offering)
            return _offering_dto(offering)
        except EnrollmentError as e:
            return ErrorDTO(str(e), "INVALID_STATE")

    def close_offering(self, offering_id: str) -> Union[OfferingDTO, ErrorDTO]:
        """Transition a CourseOffering from OPEN to CLOSED."""
        offering = self._get_offering_domain(offering_id)
        if isinstance(offering, ErrorDTO):
            return offering
        try:
            offering.close_registration()
            self._offerings.save(offering)
            return _offering_dto(offering)
        except EnrollmentError as e:
            return ErrorDTO(str(e), "INVALID_STATE")

    def mark_student_completed(
        self, student_id: str, course_code: str
    ) -> Union[StudentDTO, ErrorDTO]:
        """Record that a student finished a course, advancing their transcript."""
        student = self._get_student_domain(student_id)
        if isinstance(student, ErrorDTO):
            return student
        course = self._get_course_domain(course_code)
        if isinstance(course, ErrorDTO):
            return course
        student.mark_course_completed(course)
        self._students.save(student)
        return _student_dto(student)

    # ------------------------------------------------------------------
    # Enrollment use cases
    # ------------------------------------------------------------------

    def enroll_student(
        self, student_id: str, offering_id: str
    ) -> Union[EnrollmentResultDTO, ErrorDTO]:
        """
        Enroll a student in a course offering.

        Returns EnrollmentResultDTO on success (directly enrolled or waitlisted).
        Returns ErrorDTO if any lookup fails or a business rule is violated.
        """
        student = self._get_student_domain(student_id)
        if isinstance(student, ErrorDTO):
            return student
        offering = self._get_offering_domain(offering_id)
        if isinstance(offering, ErrorDTO):
            return offering

        active = self._offerings.find_by_semester(offering.semester)

        try:
            self._reg_service.enroll(student, offering, active)
        except EnrollmentError as e:
            return ErrorDTO(str(e), "ENROLLMENT_RULE_VIOLATION")

        self._offerings.save(offering)
        self._publisher.publish_all(offering.collect_events())

        waitlisted = offering.is_student_waitlisted(student)
        if waitlisted:
            pos = offering.waitlist.index(student) + 1
            msg = (
                f"Course full. {student.name} added to waitlist "
                f"(position {pos}) for '{offering.course.title}'."
            )
        else:
            msg = f"{student.name} enrolled in '{offering.course.title}' ({offering.semester})."

        return EnrollmentResultDTO(
            success=True, waitlisted=waitlisted, message=msg, offering=_offering_dto(offering)
        )

    def drop_student(
        self, student_id: str, offering_id: str
    ) -> Union[EnrollmentResultDTO, ErrorDTO]:
        """Drop a student from a course offering."""
        student = self._get_student_domain(student_id)
        if isinstance(student, ErrorDTO):
            return student
        offering = self._get_offering_domain(offering_id)
        if isinstance(offering, ErrorDTO):
            return offering
        try:
            self._reg_service.drop(student, offering)
        except EnrollmentError as e:
            return ErrorDTO(str(e), "ENROLLMENT_RULE_VIOLATION")

        self._offerings.save(offering)
        self._publisher.publish_all(offering.collect_events())

        return EnrollmentResultDTO(
            success=True, waitlisted=False,
            message=f"{student.name} dropped '{offering.course.title}'.",
            offering=_offering_dto(offering),
        )

    # ------------------------------------------------------------------
    # Queries — all return DTOs, never domain objects
    # ------------------------------------------------------------------

    def list_offerings(self, semester: Optional[Semester] = None) -> List[OfferingDTO]:
        """Return all offerings, optionally filtered by semester."""
        src = (
            self._offerings.find_by_semester(semester)
            if semester else self._offerings.find_all()
        )
        return [_offering_dto(o) for o in src]

    def list_students(self) -> List[StudentDTO]:
        return [_student_dto(s) for s in self._students.find_all()]

    def list_courses(self) -> List[CourseDTO]:
        return [_course_dto(c) for c in self._courses.find_all()]

    def get_student_schedule(
        self, student_id: str
    ) -> Union[List[OfferingDTO], ErrorDTO]:
        """Return all offerings a student is currently enrolled in."""
        student = self._get_student_domain(student_id)
        if isinstance(student, ErrorDTO):
            return student
        return [_offering_dto(o) for o in self._offerings.find_by_student(student_id)]

    def search_courses(self, keyword: str) -> List[CourseDTO]:
        """Return courses whose code or title contains the keyword (case-insensitive)."""
        kw = keyword.lower()
        return [
            _course_dto(c) for c in self._courses.find_all()
            if kw in c.title.lower() or kw in c.course_code.lower()
        ]

    def get_course(self, course_code: str) -> Union[CourseDTO, ErrorDTO]:
        """Return a single CourseDTO by code, or ErrorDTO if not found."""
        course = self._get_course_domain(course_code)
        if isinstance(course, ErrorDTO):
            return course
        return _course_dto(course)

    # ------------------------------------------------------------------
    # Private helpers — return domain objects OR ErrorDTO
    # ------------------------------------------------------------------

    def _get_student_domain(self, student_id: str) -> Union[Student, ErrorDTO]:
        s = self._students.find_by_id(student_id)
        return s if s else ErrorDTO(f"Student '{student_id}' not found.", "NOT_FOUND")

    def _get_course_domain(self, course_code: str) -> Union[Course, ErrorDTO]:
        c = self._courses.find_by_code(course_code)
        return c if c else ErrorDTO(f"Course '{course_code}' not found.", "NOT_FOUND")

    def _get_offering_domain(self, offering_id: str) -> Union[CourseOffering, ErrorDTO]:
        o = self._offerings.find_by_id(offering_id)
        return o if o else ErrorDTO(f"Offering '{offering_id}' not found.", "NOT_FOUND")
