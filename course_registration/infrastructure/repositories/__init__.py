"""
infrastructure/repositories/__init__.py — In-memory repository implementations.

These classes implement the repository interfaces defined in the domain layer.
They store all data in plain Python dictionaries, making them fast and
dependency-free — no database setup required.

In-memory repositories are ideal for:
  - Running the CLI or GUI without any external infrastructure.
  - Unit and integration tests that need clean, isolated state per test run.

For real-world deployment these would be swapped for SQL or NoSQL
implementations that satisfy the same abstract interfaces.  The domain and
application layers would require no changes.
"""

from __future__ import annotations
from typing import Dict, List, Optional

from course_registration.domain.entities      import Course, Instructor, Student
from course_registration.domain.aggregates    import CourseOffering
from course_registration.domain.value_objects import Semester
from course_registration.domain.repositories  import (
    StudentRepository, CourseRepository,
    InstructorRepository, CourseOfferingRepository,
)


class InMemoryStudentRepository(StudentRepository):
    """Stores Student entities in a dictionary keyed by student_id."""

    def __init__(self) -> None:
        self._store: Dict[str, Student] = {}

    def save(self, student: Student) -> None:
        self._store[student.student_id] = student

    def find_by_id(self, student_id: str) -> Optional[Student]:
        return self._store.get(student_id)

    def find_all(self) -> List[Student]:
        return list(self._store.values())

    def delete(self, student_id: str) -> None:
        self._store.pop(student_id, None)

class InMemoryCourseRepository(CourseRepository):
    """Stores Course entities in a dictionary keyed by course_code."""

    def __init__(self) -> None:
        self._store: Dict[str, Course] = {}

    def save(self, course: Course) -> None:
        self._store[course.course_code] = course

    def find_by_code(self, course_code: str) -> Optional[Course]:
        return self._store.get(course_code)

    def find_all(self) -> List[Course]:
        return list(self._store.values())

    def delete(self, course_code: str) -> None:
        """Remove the course from the store if it exists."""
        self._store.pop(course_code, None)
        
    def delete(self, offering_id: str) -> None:
        self._store.pop(offering_id, None)

    def find_by_instructor(self, instructor_id: str) -> List[CourseOffering]:
        return [o for o in self._store.values()
                if o.instructor.instructor_id == instructor_id]


class InMemoryInstructorRepository(InstructorRepository):
    """Stores Instructor entities in a dictionary keyed by instructor_id."""

    def __init__(self) -> None:
        self._store: Dict[str, Instructor] = {}

    def save(self, instructor: Instructor) -> None:
        self._store[instructor.instructor_id] = instructor

    def find_by_id(self, instructor_id: str) -> Optional[Instructor]:
        return self._store.get(instructor_id)

    def find_all(self) -> List[Instructor]:
        return list(self._store.values())
    
    def delete(self, instructor_id: str) -> None:
        self._store.pop(instructor_id, None)


class InMemoryCourseOfferingRepository(CourseOfferingRepository):
    """Stores CourseOffering aggregates in a dictionary keyed by offering_id."""

    def __init__(self) -> None:
        self._store: Dict[str, CourseOffering] = {}

    def save(self, offering: CourseOffering) -> None:
        self._store[offering.offering_id] = offering

    def find_by_id(self, offering_id: str) -> Optional[CourseOffering]:
        return self._store.get(offering_id)

    def find_by_semester(self, semester: Semester) -> List[CourseOffering]:
        """Return every offering whose semester matches the given Semester value object."""
        return [o for o in self._store.values() if o.semester == semester]

    def find_by_student(self, student_id: str) -> List[CourseOffering]:
        """Return every offering in which the student is currently enrolled."""
        return [
            o for o in self._store.values()
            if any(s.student_id == student_id for s in o.enrolled)
        ]

    def find_by_course(self, course_code: str) -> List[CourseOffering]:
        """Return every offering that references the given course code."""
        return [
            o for o in self._store.values()
            if o.course.course_code == course_code
        ]

    def delete(self, offering_id: str) -> None:
        self._store.pop(offering_id, None)

    def find_by_instructor(self, instructor_id: str) -> List[CourseOffering]:
        return [
            o for o in self._store.values()
            if o.instructor.instructor_id == instructor_id
        ]

    def find_all(self) -> List[CourseOffering]:
        return list(self._store.values())
