"""
bootstrap/__init__.py — Composition root.

The bootstrap module is the single place in the codebase that imports from
BOTH the application layer and the infrastructure layer at the same time.
Every other module only imports from layers at or below itself:

    domain          imports nothing from the project
    infrastructure  imports from domain
    application     imports from domain
    presentation    imports from application
    bootstrap       imports from application + infrastructure (intentionally)

Both the CLI and a future GUI call create_app() to receive a fully wired
RegistrationAppService.  Neither needs to know which repository implementation
or persistence backend is in use.

Seed data also lives here so that any presentation layer can call
seed_demo_data() on first run without duplicating the setup logic.
"""

from __future__ import annotations
import os
from datetime import date
from typing import Callable, Dict, List, Tuple

from course_registration.domain.value_objects import Semester, ScheduleSlot
from course_registration.domain.events        import DomainEvent
from course_registration.infrastructure.repositories import (
    InMemoryStudentRepository,
    InMemoryCourseRepository,
    InMemoryInstructorRepository,
    InMemoryCourseOfferingRepository,
)
from course_registration.infrastructure.persistence  import JsonPersistence
from course_registration.application.services        import RegistrationAppService
from course_registration.application.services.event_publisher import EventPublisher


# Default data file path — placed one directory above bootstrap/
DEFAULT_DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data.json")

# The active semester used throughout the application
DEFAULT_SEMESTER = Semester(
    semester_id="SEM-2026-SP",
    term="Spring", year=2026,
    start_date=date(2026, 1, 15),
    end_date=date(2026, 5, 31),
)


def create_app(
    data_file      : str = DEFAULT_DATA_FILE,
    event_handlers : List[Callable[[DomainEvent], None]] = None,
) -> Tuple[RegistrationAppService, JsonPersistence, Dict, Semester]:
    """
    Wire up and return (app_service, persistence, repos, semester).

    Parameters
    ----------
    data_file
        Path to the JSON persistence file.  Defaults to data.json in the
        project root directory.
    event_handlers
        List of callables that will be invoked for every domain event.
        - Pass []            for silent operation (unit tests).
        - Pass [print_fn]    for CLI output.
        - Pass [widget_fn]   for GUI log panels or status bars.

    Returns
    -------
    A tuple of (RegistrationAppService, JsonPersistence, repos dict, Semester).
    The caller retains persistence and repos to call persistence.save(repos)
    after any mutating operation.
    """
    persistence = JsonPersistence(data_file)
    repos       = persistence.load()

    publisher = EventPublisher()
    for handler in (event_handlers or []):
        publisher.subscribe(handler)

    svc = RegistrationAppService(
        student_repo    = repos["students"],
        course_repo     = repos["courses"],
        instructor_repo = repos["instructors"],
        offering_repo   = repos["offerings"],
        event_publisher = publisher,
    )

    return svc, persistence, repos, DEFAULT_SEMESTER


def seed_demo_data(svc: RegistrationAppService, semester: Semester) -> None:
    """
    Populate the system with representative demo data for first-run use.

    Extracted from the CLI so any presentation layer can call this without
    duplicating setup.  Only runs when the data file does not yet exist
    (checked by the caller before invoking this function).
    """
    # Courses — CS track with prerequisite chain, and a Maths track
    svc.add_course("CS101",   "Intro to Computer Science", credits=3)
    svc.add_course("CS201",   "Data Structures",           credits=3, prerequisite_codes=["CS101"])
    svc.add_course("CS301",   "Algorithms",                credits=3, prerequisite_codes=["CS201"])
    svc.add_course("MATH101", "Calculus I",                credits=4)
    svc.add_course("MATH201", "Calculus II",               credits=4, prerequisite_codes=["MATH101"])

    # Instructors
    svc.add_instructor("I001", "Dr. Ana Torres",  "Computer Science")
    svc.add_instructor("I002", "Dr. Luis Mendez", "Mathematics")

    # Students
    svc.add_student("S001", "Pablo Vasquez",  "Computer Science")
    svc.add_student("S002", "Natalie Bustos", "Computer Science")
    svc.add_student("S003", "Luis Garcia",    "Mathematics")

    # Give Pablo a completed CS101 so he can enroll in CS201
    svc.mark_student_completed("S001", "CS101")

    # Offerings with intentionally distinct schedules to exercise overlap detection
    svc.create_offering("OFF001", "CS101", "I001", semester, capacity=2,
        schedule=[ScheduleSlot("Monday",    "08:00", "09:30"),
                  ScheduleSlot("Wednesday", "08:00", "09:30")])
    svc.create_offering("OFF002", "CS201", "I001", semester, capacity=2,
        schedule=[ScheduleSlot("Tuesday",   "10:00", "11:30"),
                  ScheduleSlot("Thursday",  "10:00", "11:30")])
    svc.create_offering("OFF003", "MATH101", "I002", semester, capacity=3,
        schedule=[ScheduleSlot("Monday",    "10:00", "11:30"),
                  ScheduleSlot("Wednesday", "10:00", "11:30")])

    # Open all offerings so students can enroll immediately
    for oid in ["OFF001", "OFF002", "OFF003"]:
        svc.open_offering(oid)
