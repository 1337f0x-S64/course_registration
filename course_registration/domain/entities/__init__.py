"""
domain/entities/__init__.py — Domain entities.

An Entity is an object that has a unique, persistent identity.  Two Student
objects with the same student_id refer to the same student even if every
other field differs.  This is the defining difference from a Value Object,
where equality is based entirely on field values.

All entities inherit from the Entity base class, which overrides __eq__ and
__hash__ to compare identity only.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Base Entity
# ---------------------------------------------------------------------------

class Entity:
    """
    Abstract base for all domain entities.

    Subclasses must implement _identity() to return their unique identifier.
    Equality and hashing are then derived from that identifier alone, not
    from any mutable attribute.
    """

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self._identity() == other._identity()

    def __hash__(self) -> int:
        return hash(self._identity())

    def _identity(self):
        raise NotImplementedError("Subclasses must implement _identity()")


# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------

@dataclass
class Course(Entity):
    """
    A subject offered in the university catalogue.

    Identity  : course_code (e.g. "CS101") — stable across semesters.
    Behaviour : manages its own prerequisite list and exposes update methods
                so changes always go through the entity, not raw field writes.
    """
    course_code   : str
    title         : str
    credits       : int
    prerequisites : List[Course] = field(default_factory=list)

    def _identity(self):
        return self.course_code

    # ------------------------------------------------------------------
    # Prerequisite management
    # ------------------------------------------------------------------

    def add_prerequisite(self, course: Course) -> None:
        """Register a course that must be completed before this one."""
        if course not in self.prerequisites:
            self.prerequisites.append(course)

    def remove_prerequisite(self, course: Course) -> None:
        """Remove a course from the prerequisites list, if present."""
        if course in self.prerequisites:
            self.prerequisites.remove(course)

    def clear_prerequisites(self) -> None:
        """Remove all prerequisites from this course."""
        self.prerequisites.clear()

    # ------------------------------------------------------------------
    # Update behaviour
    # ------------------------------------------------------------------

    def update(
        self,
        title           : str = None,
        credits         : int = None,
        new_prereq_codes: List[str] = None,
        all_courses     : dict = None,
    ) -> None:
        """
        Update mutable fields on this Course.

        Parameters
        ----------
        title
            New human-readable name.  Pass None to leave unchanged.
        credits
            New credit value.  Must be a positive integer.  Pass None to
            leave unchanged.
        new_prereq_codes
            If provided, replaces the entire prerequisite list with the
            courses whose codes appear in this list.  Pass None to leave
            prerequisites unchanged.  Pass [] to clear all prerequisites.
        all_courses
            Dict[course_code, Course] needed to resolve new_prereq_codes.
            Required when new_prereq_codes is not None.

        Raises
        ------
        ValueError
            When credits is not a positive integer, or a prerequisite code
            cannot be resolved.
        """
        if title is not None:
            if not title.strip():
                raise ValueError("Course title cannot be blank.")
            self.title = title.strip()

        if credits is not None:
            if not isinstance(credits, int) or credits < 1:
                raise ValueError("Credits must be a positive integer.")
            self.credits = credits

        if new_prereq_codes is not None:
            if all_courses is None:
                raise ValueError("all_courses dict is required when updating prerequisites.")
            resolved = []
            for code in new_prereq_codes:
                if code == self.course_code:
                    raise ValueError(f"A course cannot be its own prerequisite ({code}).")
                prereq = all_courses.get(code)
                if prereq is None:
                    raise ValueError(f"Prerequisite course '{code}' not found.")
                resolved.append(prereq)
            self.prerequisites = resolved

    def __str__(self) -> str:
        return f"{self.course_code} - {self.title} ({self.credits} cr)"

    def __repr__(self) -> str:
        return f"Course(code={self.course_code!r})"


# ---------------------------------------------------------------------------
# Instructor
# ---------------------------------------------------------------------------

@dataclass
class Instructor(Entity):
    """
    A faculty member who teaches CourseOfferings.

    Identity : instructor_id — assigned by the university HR system.
    """
    instructor_id : str
    name          : str
    department    : str

    def _identity(self):
        return self.instructor_id
    
    def update(self, name: str = None, department: str = None) -> None:
        if name is not None:
            if not name.strip():
                raise ValueError("Instructor name cannot be blank.")
            self.name = name.strip()
        if department is not None:
            if not department.strip():
                raise ValueError("Department cannot be blank.")
            self.department = department.strip()

    def __str__(self) -> str:
        return f"Prof. {self.name} ({self.department})"
    
    


# ---------------------------------------------------------------------------
# Student
# ---------------------------------------------------------------------------

@dataclass
class Student(Entity):
    """
    A person enrolled at the university.

    Identity  : student_id — assigned at admission.
    Behaviour : tracks completed courses, which drives prerequisite validation
                and enforces the per-semester credit-load limit.

    MAX_CREDITS_PER_SEMESTER is a business rule constant defined here so the
    rule travels with the data it governs.
    """
    student_id        : str
    name              : str
    program           : str
    completed_courses : List[Course] = field(default_factory=list)

    # Business rule: no student may exceed 18 credits in a single semester.
    MAX_CREDITS_PER_SEMESTER: int = field(default=18, init=False, repr=False)

    def _identity(self):
        return self.student_id

    def has_completed(self, course: Course) -> bool:
        """Return True if this student has already finished the given course."""
        return course in self.completed_courses

    def meets_prerequisites(self, course: Course) -> bool:
        """
        Return True when every prerequisite for the given course has been
        completed.  A course with no prerequisites is open to all students.
        """
        return all(self.has_completed(prereq) for prereq in course.prerequisites)

    def mark_course_completed(self, course: Course) -> None:
        """Record that the student successfully finished a course."""
        if course not in self.completed_courses:
            self.completed_courses.append(course)

    def update(self, name: str = None, program: str = None) -> None:
        if name is not None:
            if not name.strip():
                raise ValueError("Student name cannot be blank.")
            self.name = name.strip()
        if program is not None:
            if not program.strip():
                raise ValueError("Program cannot be blank.")
            self.program = program.strip()
    
    def __str__(self) -> str:
        return f"{self.name} [{self.student_id}] - {self.program}"
