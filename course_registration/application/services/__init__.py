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
update_course()  — change title, credits, and/or prerequisites
delete_course()  — remove a course; blocked if active offerings exist

Student management methods
--------------------------
update_student() — change name and/or program
delete_student() — remove a student; blocked if enrolled in any offering

Instructor management methods
------------------------------
update_instructor() — change name and/or department
delete_instructor() — remove an instructor; blocked if assigned to any offering

Offering management methods
----------------------------
update_offering() — change capacity and/or schedule; only while SCHEDULED
delete_offering() — remove an offering; blocked if students are enrolled/waitlisted
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
    StudentUpdated, StudentDeleted,
    InstructorUpdated, InstructorDeleted,
    OfferingUpdated, OfferingDeleted,
)
from course_registration.application.dtos import (
    CourseDTO, InstructorDTO, StudentDTO,
    ScheduleSlotDTO, OfferingDTO,
    EnrollmentResultDTO,
    CourseManagementResultDTO,
    StudentManagementResultDTO,
    InstructorManagementResultDTO,
    OfferingManagementResultDTO,
    ErrorDTO,
)
from course_registration.application.services.event_publisher import EventPublisher


# ---------------------------------------------------------------------------
# DTO assemblers — private helpers
# ---------------------------------------------------------------------------

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
        if self._courses.find_by_code(course_code):
            return ErrorDTO(
                f"A course with code '{course_code}' already exists.",
                "DUPLICATE_COURSE_CODE",
            )

        course = Course(course_code=course_code, title=title, credits=credits)

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

        Pass None for any parameter to leave it unchanged.
        Pass [] for new_prereq_codes to clear all prerequisites.

        Returns CourseManagementResultDTO(action="updated") on success.
        Returns ErrorDTO on validation failure or if the course is not found.
        """
        course = self._get_course_domain(course_code)
        if isinstance(course, ErrorDTO):
            return course

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

        Blocked if any CourseOffering references this course, or if any other
        course lists it as a prerequisite.

        Returns CourseManagementResultDTO(action="deleted", course=None) on success.
        """
        course = self._get_course_domain(course_code)
        if isinstance(course, ErrorDTO):
            return course

        offerings_using = self._offerings.find_by_course(course_code)
        if offerings_using:
            offering_ids = ", ".join(o.offering_id for o in offerings_using)
            return ErrorDTO(
                f"Cannot delete '{course_code}': it is referenced by "
                f"offering(s) {offering_ids}. Remove those offerings first.",
                "COURSE_IN_USE",
            )

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

        title = course.title
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
    # Student management — add, update, delete
    # ------------------------------------------------------------------

    def add_student(
        self, student_id: str, name: str, program: str
    ) -> Union[StudentManagementResultDTO, ErrorDTO]:
        """
        Create and persist a new Student.

        Returns StudentManagementResultDTO(action="created") on success.
        Returns ErrorDTO with code DUPLICATE_STUDENT_ID if the ID already exists.
        """
        if self._students.find_by_id(student_id):
            return ErrorDTO(
                f"A student with ID '{student_id}' already exists.",
                "DUPLICATE_STUDENT_ID",
            )

        student = Student(student_id=student_id, name=name, program=program)
        self._students.save(student)

        return StudentManagementResultDTO(
            success=True, action="created",
            message=f"Student '{name}' ({student_id}) added.",
            student=_student_dto(student),
        )

    def update_student(
        self,
        student_id   : str,
        new_name     : str = None,
        new_program  : str = None,
    ) -> Union[StudentManagementResultDTO, ErrorDTO]:
        """
        Update an existing Student's name and/or program.

        Pass None for any parameter to leave it unchanged.

        Returns StudentManagementResultDTO(action="updated") on success.
        Returns ErrorDTO on validation failure or if the student is not found.
        """
        student = self._get_student_domain(student_id)
        if isinstance(student, ErrorDTO):
            return student

        try:
            student.update(name=new_name, program=new_program)
        except ValueError as e:
            return ErrorDTO(str(e), "VALIDATION_ERROR")

        self._students.save(student)
        self._publisher.publish(StudentUpdated(
            occurred_on=datetime.now(),
            student_id=student.student_id,
            name=student.name,
        ))

        return StudentManagementResultDTO(
            success=True, action="updated",
            message=f"Student '{student_id}' updated successfully.",
            student=_student_dto(student),
        )

    def delete_student(
        self, student_id: str
    ) -> Union[StudentManagementResultDTO, ErrorDTO]:
        """
        Permanently delete a Student from the system.

        Blocked if the student is currently enrolled in or waitlisted for any
        offering.  Dropping them first is required so that waitlist promotion
        logic fires correctly and enrollment counts stay accurate.

        Returns StudentManagementResultDTO(action="deleted", student=None) on success.
        Returns ErrorDTO with code STUDENT_IN_USE if enrollments exist.
        """
        student = self._get_student_domain(student_id)
        if isinstance(student, ErrorDTO):
            return student

        active_offerings = self._offerings.find_by_student(student_id)
        if active_offerings:
            offering_ids = ", ".join(o.offering_id for o in active_offerings)
            return ErrorDTO(
                f"Cannot delete '{student_id}': they are enrolled in "
                f"offering(s) {offering_ids}. Drop them first.",
                "STUDENT_IN_USE",
            )

        # Also check waitlists — find_by_student only returns enrolled offerings.
        waitlisted = [
            o for o in self._offerings.find_all()
            if any(s.student_id == student_id for s in o.waitlist)
        ]
        if waitlisted:
            offering_ids = ", ".join(o.offering_id for o in waitlisted)
            return ErrorDTO(
                f"Cannot delete '{student_id}': they are on the waitlist for "
                f"offering(s) {offering_ids}. Drop them first.",
                "STUDENT_IN_USE",
            )

        name = student.name
        self._students.delete(student_id)
        self._publisher.publish(StudentDeleted(
            occurred_on=datetime.now(), student_id=student_id, name=name
        ))

        return StudentManagementResultDTO(
            success=True, action="deleted",
            message=f"Student '{student_id} - {name}' removed from the system.",
            student=None,
        )

    # ------------------------------------------------------------------
    # Instructor management — add, update, delete
    # ------------------------------------------------------------------

    def add_instructor(
        self, instructor_id: str, name: str, department: str
    ) -> Union[InstructorManagementResultDTO, ErrorDTO]:
        """
        Create and persist a new Instructor.

        Returns InstructorManagementResultDTO(action="created") on success.
        Returns ErrorDTO with code DUPLICATE_INSTRUCTOR_ID if the ID already exists.
        """
        if self._instructors.find_by_id(instructor_id):
            return ErrorDTO(
                f"An instructor with ID '{instructor_id}' already exists.",
                "DUPLICATE_INSTRUCTOR_ID",
            )

        instructor = Instructor(instructor_id=instructor_id, name=name, department=department)
        self._instructors.save(instructor)

        return InstructorManagementResultDTO(
            success=True, action="created",
            message=f"Instructor '{name}' ({instructor_id}) added.",
            instructor=_instructor_dto(instructor),
        )

    def update_instructor(
        self,
        instructor_id  : str,
        new_name       : str = None,
        new_department : str = None,
    ) -> Union[InstructorManagementResultDTO, ErrorDTO]:
        """
        Update an existing Instructor's name and/or department.

        Pass None for any parameter to leave it unchanged.

        Returns InstructorManagementResultDTO(action="updated") on success.
        Returns ErrorDTO on validation failure or if the instructor is not found.
        """
        instructor = self._get_instructor_domain(instructor_id)
        if isinstance(instructor, ErrorDTO):
            return instructor

        try:
            instructor.update(name=new_name, department=new_department)
        except ValueError as e:
            return ErrorDTO(str(e), "VALIDATION_ERROR")

        self._instructors.save(instructor)
        self._publisher.publish(InstructorUpdated(
            occurred_on=datetime.now(),
            instructor_id=instructor.instructor_id,
            name=instructor.name,
        ))

        return InstructorManagementResultDTO(
            success=True, action="updated",
            message=f"Instructor '{instructor_id}' updated successfully.",
            instructor=_instructor_dto(instructor),
        )

    def delete_instructor(
        self, instructor_id: str
    ) -> Union[InstructorManagementResultDTO, ErrorDTO]:
        """
        Permanently delete an Instructor from the system.

        Blocked if any CourseOffering (in any status) references this instructor.
        Reassign or delete those offerings first.

        Returns InstructorManagementResultDTO(action="deleted", instructor=None) on success.
        Returns ErrorDTO with code INSTRUCTOR_IN_USE if offerings exist.
        """
        instructor = self._get_instructor_domain(instructor_id)
        if isinstance(instructor, ErrorDTO):
            return instructor

        offerings_using = self._offerings.find_by_instructor(instructor_id)
        if offerings_using:
            offering_ids = ", ".join(o.offering_id for o in offerings_using)
            return ErrorDTO(
                f"Cannot delete '{instructor_id}': they are assigned to "
                f"offering(s) {offering_ids}. Remove those offerings first.",
                "INSTRUCTOR_IN_USE",
            )

        name = instructor.name
        self._instructors.delete(instructor_id)
        self._publisher.publish(InstructorDeleted(
            occurred_on=datetime.now(), instructor_id=instructor_id, name=name
        ))

        return InstructorManagementResultDTO(
            success=True, action="deleted",
            message=f"Instructor '{instructor_id} - {name}' removed from the system.",
            instructor=None,
        )

    # ------------------------------------------------------------------
    # Offering management — create, update, delete
    # (open/close lifecycle remain as separate methods below)
    # ------------------------------------------------------------------

    def create_offering(
        self,
        offering_id   : str,
        course_code   : str,
        instructor_id : str,
        semester      : Semester,
        capacity      : int,
        schedule      : List[ScheduleSlot] = None,
    ) -> Union[OfferingManagementResultDTO, ErrorDTO]:
        """
        Create and persist a new CourseOffering.

        Returns OfferingManagementResultDTO(action="created") on success.
        Returns ErrorDTO if the course or instructor is not found, or if the
        offering_id already exists.
        """
        if self._offerings.find_by_id(offering_id):
            return ErrorDTO(
                f"An offering with ID '{offering_id}' already exists.",
                "DUPLICATE_OFFERING_ID",
            )

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

        return OfferingManagementResultDTO(
            success=True, action="created",
            message=f"Offering '{offering_id}' for '{course.title}' created.",
            offering=_offering_dto(offering),
        )

    def update_offering(
        self,
        offering_id  : str,
        new_capacity : int = None,
        new_schedule : List[ScheduleSlot] = None,
    ) -> Union[OfferingManagementResultDTO, ErrorDTO]:
        """
        Update a CourseOffering's capacity and/or schedule.

        Only permitted while the offering is in SCHEDULED status (before it
        has been opened for enrollment).  Once students can enroll, changes
        to capacity or schedule could silently violate their expectations.

        Pass None for any parameter to leave it unchanged.

        Returns OfferingManagementResultDTO(action="updated") on success.
        Returns ErrorDTO with code INVALID_STATE if the offering is not SCHEDULED,
        or VALIDATION_ERROR if the new values fail domain rules.
        """
        offering = self._get_offering_domain(offering_id)
        if isinstance(offering, ErrorDTO):
            return offering

        try:
            offering.update(capacity=new_capacity, schedule=new_schedule)
        except EnrollmentError as e:
            return ErrorDTO(str(e), "INVALID_STATE")

        self._offerings.save(offering)
        self._publisher.publish(OfferingUpdated(
            occurred_on=datetime.now(),
            offering_id=offering.offering_id,
            course_code=offering.course.course_code,
        ))

        return OfferingManagementResultDTO(
            success=True, action="updated",
            message=f"Offering '{offering_id}' updated successfully.",
            offering=_offering_dto(offering),
        )

    def delete_offering(
        self, offering_id: str
    ) -> Union[OfferingManagementResultDTO, ErrorDTO]:
        """
        Permanently delete a CourseOffering.

        Blocked if any students are currently enrolled in or waitlisted for
        the offering.  Drop all students first, or close the offering and
        then delete it if enrollment tracking is no longer needed.

        Returns OfferingManagementResultDTO(action="deleted", offering=None) on success.
        Returns ErrorDTO with code OFFERING_IN_USE if students are attached.
        """
        offering = self._get_offering_domain(offering_id)
        if isinstance(offering, ErrorDTO):
            return offering

        if offering.enrolled:
            names = ", ".join(s.name for s in offering.enrolled)
            return ErrorDTO(
                f"Cannot delete '{offering_id}': {len(offering.enrolled)} student(s) "
                f"are enrolled ({names}). Drop them first.",
                "OFFERING_IN_USE",
            )
        if offering.waitlist:
            names = ", ".join(s.name for s in offering.waitlist)
            return ErrorDTO(
                f"Cannot delete '{offering_id}': {len(offering.waitlist)} student(s) "
                f"are on the waitlist ({names}). Drop them first.",
                "OFFERING_IN_USE",
            )

        course_code = offering.course.course_code
        self._offerings.delete(offering_id)
        self._publisher.publish(OfferingDeleted(
            occurred_on=datetime.now(),
            offering_id=offering_id,
            course_code=course_code,
        ))

        return OfferingManagementResultDTO(
            success=True, action="deleted",
            message=f"Offering '{offering_id}' deleted.",
            offering=None,
        )

    # ------------------------------------------------------------------
    # Offering lifecycle — open and close
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Other setup commands
    # ------------------------------------------------------------------

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

    def list_instructors(self) -> List[InstructorDTO]:
        return [_instructor_dto(i) for i in self._instructors.find_all()]

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

    def get_student(self, student_id: str) -> Union[StudentDTO, ErrorDTO]:
        """Return a single StudentDTO by ID, or ErrorDTO if not found."""
        student = self._get_student_domain(student_id)
        if isinstance(student, ErrorDTO):
            return student
        return _student_dto(student)

    def get_instructor(self, instructor_id: str) -> Union[InstructorDTO, ErrorDTO]:
        """Return a single InstructorDTO by ID, or ErrorDTO if not found."""
        instructor = self._get_instructor_domain(instructor_id)
        if isinstance(instructor, ErrorDTO):
            return instructor
        return _instructor_dto(instructor)

    def get_offering(self, offering_id: str) -> Union[OfferingDTO, ErrorDTO]:
        """Return a single OfferingDTO by ID, or ErrorDTO if not found."""
        offering = self._get_offering_domain(offering_id)
        if isinstance(offering, ErrorDTO):
            return offering
        return _offering_dto(offering)

    # ------------------------------------------------------------------
    # Private helpers — return domain objects OR ErrorDTO
    # ------------------------------------------------------------------

    def _get_student_domain(self, student_id: str) -> Union[Student, ErrorDTO]:
        s = self._students.find_by_id(student_id)
        return s if s else ErrorDTO(f"Student '{student_id}' not found.", "NOT_FOUND")

    def _get_course_domain(self, course_code: str) -> Union[Course, ErrorDTO]:
        c = self._courses.find_by_code(course_code)
        return c if c else ErrorDTO(f"Course '{course_code}' not found.", "NOT_FOUND")

    def _get_instructor_domain(self, instructor_id: str) -> Union[Instructor, ErrorDTO]:
        i = self._instructors.find_by_id(instructor_id)
        return i if i else ErrorDTO(f"Instructor '{instructor_id}' not found.", "NOT_FOUND")

    def _get_offering_domain(self, offering_id: str) -> Union[CourseOffering, ErrorDTO]:
        o = self._offerings.find_by_id(offering_id)
        return o if o else ErrorDTO(f"Offering '{offering_id}' not found.", "NOT_FOUND")