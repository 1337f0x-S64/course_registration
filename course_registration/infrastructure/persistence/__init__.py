"""
infrastructure/persistence/__init__.py — JSON file persistence.

JsonPersistence serialises the full state of all repositories to a single
JSON file and deserialises it on startup.  This means data survives between
sessions without requiring a database server.

Design notes
------------
- Serialisation converts domain objects to plain dicts of primitives.
- Deserialisation reconstructs domain objects in dependency order:
  courses first (needed for prerequisites), then instructors, then students,
  then offerings (which reference all of the above).
- On load, enrolled and waitlist membership is restored by appending directly
  to the aggregate's private lists, bypassing invariant checks that would
  otherwise reject already-valid historical state.
"""

from __future__ import annotations
import json
import os
from datetime import date
from typing import Dict

from course_registration.domain.entities      import Course, Instructor, Student
from course_registration.domain.aggregates    import CourseOffering
from course_registration.domain.value_objects import Semester, ScheduleSlot, OfferingStatus
from course_registration.infrastructure.repositories import (
    InMemoryStudentRepository,
    InMemoryCourseRepository,
    InMemoryInstructorRepository,
    InMemoryCourseOfferingRepository,
)


class JsonPersistence:
    """
    Saves and loads the entire system state to and from a JSON file.

    Usage
    -----
        persistence = JsonPersistence("data.json")
        repos = persistence.load()       # populate repos from disk
        # ... make changes via the app service ...
        persistence.save(repos)          # write updated state back to disk
    """

    def __init__(self, filepath: str = "data.json") -> None:
        self.filepath = filepath

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self, repos: Dict) -> None:
        """Serialise all repositories to the JSON file."""
        data = {
            "students"    : self._ser_students(repos["students"].find_all()),
            "courses"     : self._ser_courses(repos["courses"].find_all()),
            "instructors" : self._ser_instructors(repos["instructors"].find_all()),
            "offerings"   : self._ser_offerings(repos["offerings"].find_all()),
        }
        with open(self.filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _ser_students(self, students):
        return [
            {
                "student_id"        : s.student_id,
                "name"              : s.name,
                "program"           : s.program,
                "completed_courses" : [c.course_code for c in s.completed_courses],
            }
            for s in students
        ]

    def _ser_courses(self, courses):
        return [
            {
                "course_code"   : c.course_code,
                "title"         : c.title,
                "credits"       : c.credits,
                "prerequisites" : [p.course_code for p in c.prerequisites],
            }
            for c in courses
        ]

    def _ser_instructors(self, instructors):
        return [
            {
                "instructor_id" : i.instructor_id,
                "name"          : i.name,
                "department"    : i.department,
            }
            for i in instructors
        ]

    def _ser_offerings(self, offerings):
        return [
            {
                "offering_id"   : o.offering_id,
                "course_code"   : o.course.course_code,
                "instructor_id" : o.instructor.instructor_id,
                "semester" : {
                    "semester_id" : o.semester.semester_id,
                    "term"        : o.semester.term,
                    "year"        : o.semester.year,
                    "start_date"  : str(o.semester.start_date),
                    "end_date"    : str(o.semester.end_date),
                },
                "capacity" : o.capacity,
                "status"   : o.status.value,
                "schedule" : [
                    {"day": s.day, "start_time": s.start_time, "end_time": s.end_time}
                    for s in o.schedule
                ],
                "enrolled"  : [s.student_id for s in o.enrolled],
                "waitlist"  : [s.student_id for s in o.waitlist],
            }
            for o in offerings
        ]

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self) -> Dict:
        """
        Deserialise data from the JSON file into populated repository instances.
        Returns a dict with keys: students, courses, instructors, offerings.
        If the file does not exist, returns empty repositories ready for seeding.
        """
        student_repo    = InMemoryStudentRepository()
        course_repo     = InMemoryCourseRepository()
        instructor_repo = InMemoryInstructorRepository()
        offering_repo   = InMemoryCourseOfferingRepository()

        if not os.path.exists(self.filepath):
            return {
                "students": student_repo, "courses": course_repo,
                "instructors": instructor_repo, "offerings": offering_repo,
            }

        with open(self.filepath) as f:
            data = json.load(f)

        # Load courses first so prerequisite references can be resolved
        course_map: Dict[str, Course] = {}
        for c in data.get("courses", []):
            course = Course(course_code=c["course_code"], title=c["title"], credits=c["credits"])
            course_map[course.course_code] = course
            course_repo.save(course)

        # Wire up prerequisites after all courses are in the map
        for c in data.get("courses", []):
            for code in c["prerequisites"]:
                if code in course_map:
                    course_map[c["course_code"]].add_prerequisite(course_map[code])

        # Load instructors
        instructor_map: Dict[str, Instructor] = {}
        for i in data.get("instructors", []):
            inst = Instructor(instructor_id=i["instructor_id"], name=i["name"], department=i["department"])
            instructor_map[inst.instructor_id] = inst
            instructor_repo.save(inst)

        # Load students, resolving completed_courses references
        student_map: Dict[str, Student] = {}
        for s in data.get("students", []):
            student = Student(
                student_id=s["student_id"],
                name=s["name"],
                program=s["program"],
                completed_courses=[
                    course_map[code] for code in s["completed_courses"] if code in course_map
                ],
            )
            student_map[student.student_id] = student
            student_repo.save(student)

        # Load offerings and restore enrolled / waitlist state
        for o in data.get("offerings", []):
            sd = o["semester"]
            semester = Semester(
                semester_id=sd["semester_id"], term=sd["term"], year=sd["year"],
                start_date=date.fromisoformat(sd["start_date"]),
                end_date=date.fromisoformat(sd["end_date"]),
            )
            offering = CourseOffering(
                offering_id=o["offering_id"],
                course=course_map[o["course_code"]],
                instructor=instructor_map[o["instructor_id"]],
                semester=semester,
                capacity=o["capacity"],
                schedule=[
                    ScheduleSlot(day=s["day"], start_time=s["start_time"], end_time=s["end_time"])
                    for s in o["schedule"]
                ],
                status=OfferingStatus(o["status"]),
            )
            # Bypass invariant checks when restoring already-valid historical state
            for sid in o.get("enrolled", []):
                if sid in student_map:
                    offering._enrolled.append(student_map[sid])
            for sid in o.get("waitlist", []):
                if sid in student_map:
                    offering._waitlist.append(student_map[sid])
            offering_repo.save(offering)

        return {
            "students": student_repo, "courses": course_repo,
            "instructors": instructor_repo, "offerings": offering_repo,
        }
