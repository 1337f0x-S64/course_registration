"""
domain/repositories/__init__.py — Repository interfaces.

A Repository provides a collection-like abstraction for loading and saving
aggregates and entities.  The domain layer defines ONLY the interface (an
abstract base class).  Concrete implementations live in the infrastructure
layer.

This separation follows the Dependency Inversion Principle: the domain depends
on an abstraction it defines, not on any concrete storage technology.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional

from course_registration.domain.entities      import Course, Instructor, Student
from course_registration.domain.aggregates    import CourseOffering
from course_registration.domain.value_objects import Semester


class StudentRepository(ABC):
    """Interface for storing and retrieving Student entities."""

    @abstractmethod
    def save(self, student: Student) -> None:
        """Insert or update a Student record."""

    @abstractmethod
    def find_by_id(self, student_id: str) -> Optional[Student]:
        """Return the Student with this ID, or None if not found."""

    @abstractmethod
    def find_all(self) -> List[Student]:
        """Return every Student in the system."""


class CourseRepository(ABC):
    """Interface for storing and retrieving Course entities."""

    @abstractmethod
    def save(self, course: Course) -> None:
        """Insert or update a Course record."""

    @abstractmethod
    def find_by_code(self, course_code: str) -> Optional[Course]:
        """Return the Course with this code, or None."""

    @abstractmethod
    def find_all(self) -> List[Course]:
        """Return every Course in the catalogue."""

    @abstractmethod
    def delete(self, course_code: str) -> None:
        """
        Permanently remove a Course from the repository.

        The application service is responsible for checking that no active
        CourseOfferings reference this course before calling delete().
        """


class InstructorRepository(ABC):
    """Interface for storing and retrieving Instructor entities."""

    @abstractmethod
    def save(self, instructor: Instructor) -> None:
        """Insert or update an Instructor record."""

    @abstractmethod
    def find_by_id(self, instructor_id: str) -> Optional[Instructor]:
        """Return the Instructor with this ID, or None."""

    @abstractmethod
    def find_all(self) -> List[Instructor]:
        """Return every Instructor."""


class CourseOfferingRepository(ABC):
    """Interface for storing and retrieving CourseOffering aggregates."""

    @abstractmethod
    def save(self, offering: CourseOffering) -> None:
        """Insert or update a CourseOffering record."""

    @abstractmethod
    def find_by_id(self, offering_id: str) -> Optional[CourseOffering]:
        """Return the CourseOffering with this ID, or None."""

    @abstractmethod
    def find_by_semester(self, semester: Semester) -> List[CourseOffering]:
        """Return all offerings scheduled for the given Semester."""

    @abstractmethod
    def find_by_student(self, student_id: str) -> List[CourseOffering]:
        """Return all offerings where the student is currently enrolled."""

    @abstractmethod
    def find_by_course(self, course_code: str) -> List[CourseOffering]:
        """
        Return all offerings that reference this course code.
        Used by the application service to check for active offerings
        before deleting a course.
        """

    @abstractmethod
    def find_all(self) -> List[CourseOffering]:
        """Return every CourseOffering in the system."""
