"""
presentation/cli/__init__.py — CLI presentation layer.

The CLI has exactly three responsibilities:
  1. Call bootstrap.create_app() to receive a fully wired service.
  2. Collect raw input from the user via input().
  3. Format the DTOs returned by the service for display on the terminal.

It contains ZERO business logic and ZERO domain imports.

Submenus
--------
Option 8  — Course management     (add / edit / delete)
Option 9  — Student management    (add / edit / delete)
Option 10 — Instructor management (add / edit / delete)
Option 11 — Offering management   (create / edit / open / close / delete)
"""

from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from course_registration.domain.events    import DomainEvent
from course_registration.domain.value_objects import ScheduleSlot, Semester
from course_registration.application.dtos import (
    OfferingDTO, StudentDTO, CourseDTO, InstructorDTO,
    CourseManagementResultDTO, StudentManagementResultDTO,
    InstructorManagementResultDTO, OfferingManagementResultDTO,
    EnrollmentResultDTO, ErrorDTO,
)
from course_registration.bootstrap import create_app, seed_demo_data, DEFAULT_SEMESTER


# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------

def _cli_event_handler(event: DomainEvent) -> None:
    """Print a one-line log entry for every domain event that fires."""
    name = event.__class__.__name__
    if hasattr(event, "student_id") and hasattr(event, "course_code"):
        print(f"  [EVENT] {name}: student={event.student_id}, course={event.course_code}")
    elif hasattr(event, "student_id"):
        print(f"  [EVENT] {name}: student={event.student_id}")
    elif hasattr(event, "instructor_id"):
        print(f"  [EVENT] {name}: instructor={event.instructor_id}")
    elif hasattr(event, "offering_id"):
        print(f"  [EVENT] {name}: offering={event.offering_id}")
    elif hasattr(event, "course_code"):
        print(f"  [EVENT] {name}: course={event.course_code}")
    else:
        print(f"  [EVENT] {name}")


# ---------------------------------------------------------------------------
# DTO formatters
# ---------------------------------------------------------------------------

def _fmt_offering(o: OfferingDTO) -> str:
    seats = f"{o.enrolled_count}/{o.capacity}"
    wl    = f"  WL:{o.waitlist_count}" if o.waitlist_count else ""
    sched = ", ".join(str(s) for s in o.schedule) or "TBD"
    return (
        f"  [{o.offering_id}] {o.course.course_code} - {o.course.title}\n"
        f"       Instructor : {o.instructor.name}\n"
        f"       Schedule   : {sched}\n"
        f"       Seats      : {seats}{wl}  |  Status: {o.status}"
    )

def _fmt_student(s: StudentDTO) -> str:
    done = ", ".join(s.completed_courses) or "none"
    return (
        f"  [{s.student_id}] {s.name} - {s.program}\n"
        f"       Completed: {done}"
    )

def _fmt_course(c: CourseDTO) -> str:
    prereqs = ", ".join(c.prerequisites) or "none"
    return (
        f"  [{c.course_code}] {c.title}\n"
        f"       Credits      : {c.credits}\n"
        f"       Prerequisites: {prereqs}"
    )

def _fmt_instructor(i: InstructorDTO) -> str:
    return (
        f"  [{i.instructor_id}] {i.name}\n"
        f"       Department: {i.department}"
    )

def _header(title: str) -> None:
    print(f"\n{chr(9472)*55}\n  {title}\n{chr(9472)*55}")


# ---------------------------------------------------------------------------
# Schedule slot parser
# ---------------------------------------------------------------------------

def _parse_schedule(raw: str) -> tuple[list[ScheduleSlot], str]:
    """
    Parse a comma-separated schedule string into ScheduleSlot objects.

    Accepts entries like:  Monday 08:00-09:30, Wednesday 08:00-09:30
    Returns (slots, error_message).  error_message is empty on success.
    """
    if not raw.strip():
        return [], ""

    slots = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split()
        if len(tokens) != 2 or "-" not in tokens[1]:
            return [], (
                f"Cannot parse '{part}'. "
                "Use format: Monday 08:00-09:30"
            )
        day = tokens[0].capitalize()
        times = tokens[1].split("-")
        if len(times) != 2:
            return [], f"Invalid time range in '{part}'. Use HH:MM-HH:MM."
        slots.append(ScheduleSlot(day=day, start_time=times[0], end_time=times[1]))
    return slots, ""


# ---------------------------------------------------------------------------
# Course management submenu
# ---------------------------------------------------------------------------

def _course_management_menu(svc, persistence, repos) -> None:
    while True:
        _header("Course Management")
        print("  1. List all courses")
        print("  2. Add a course")
        print("  3. Edit a course")
        print("  4. Delete a course")
        print("  0. Back\n")

        choice = input("  Select option: ").strip()

        if choice == "1":
            _header("Course Catalogue")
            courses = svc.list_courses()
            if not courses:
                print("  (no courses in the catalogue)")
            for c in courses:
                print(_fmt_course(c))
                print()

        elif choice == "2":
            _header("Add Course")
            code        = input("  Course code  (e.g. CS401): ").strip().upper()
            title       = input("  Title: ").strip()
            credits_raw = input("  Credits (integer): ").strip()
            prereq_raw  = input("  Prerequisites (comma-separated codes, or blank): ").strip()

            try:
                credits = int(credits_raw)
            except ValueError:
                print("\n  x Credits must be a whole number.")
                input("\n  Press Enter to continue...")
                continue

            prereq_codes = (
                [p.strip().upper() for p in prereq_raw.split(",") if p.strip()]
                if prereq_raw else []
            )

            result = svc.add_course(code, title, credits, prereq_codes)
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                print(f"\n  + {result.message}")
                print(_fmt_course(result.course))
                persistence.save(repos)

        elif choice == "3":
            _header("Edit Course")
            for c in svc.list_courses():
                print(_fmt_course(c))
                print()

            code = input("  Course code to edit: ").strip().upper()
            existing = svc.get_course(code)
            if isinstance(existing, ErrorDTO):
                print(f"\n  x {existing.message}")
                input("\n  Press Enter to continue...")
                continue

            print(f"\n  Current values for {code}:")
            print(_fmt_course(existing))
            print("\n  Press Enter on any field to leave it unchanged.\n")

            new_title   = input(f"  New title [{existing.title}]: ").strip()
            credits_raw = input(f"  New credits [{existing.credits}]: ").strip()
            prereq_raw  = input(
                f"  New prerequisites [{', '.join(existing.prerequisites) or 'none'}] "
                "(comma-separated, or CLEAR): "
            ).strip()

            parsed_title   = new_title if new_title else None
            parsed_credits = None
            if credits_raw:
                try:
                    parsed_credits = int(credits_raw)
                except ValueError:
                    print("\n  x Credits must be a whole number.")
                    input("\n  Press Enter to continue...")
                    continue

            parsed_prereqs = None
            if prereq_raw.upper() == "CLEAR":
                parsed_prereqs = []
            elif prereq_raw:
                parsed_prereqs = [p.strip().upper() for p in prereq_raw.split(",") if p.strip()]

            result = svc.update_course(
                code,
                new_title=parsed_title,
                new_credits=parsed_credits,
                new_prereq_codes=parsed_prereqs,
            )
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                print(f"\n  + {result.message}")
                print(_fmt_course(result.course))
                persistence.save(repos)

        elif choice == "4":
            _header("Delete Course")
            for c in svc.list_courses():
                print(_fmt_course(c))
                print()

            code = input("  Course code to delete: ").strip().upper()
            existing = svc.get_course(code)
            if isinstance(existing, ErrorDTO):
                print(f"\n  x {existing.message}")
                input("\n  Press Enter to continue...")
                continue

            print(f"\n  About to delete:")
            print(_fmt_course(existing))
            confirm = input("\n  Type YES to confirm: ").strip()

            if confirm != "YES":
                print("  Deletion cancelled.")
            else:
                result = svc.delete_course(code)
                if isinstance(result, ErrorDTO):
                    print(f"\n  x {result.message}")
                else:
                    print(f"\n  + {result.message}")
                    persistence.save(repos)

        elif choice == "0":
            break
        else:
            print("  Invalid option.")

        input("\n  Press Enter to continue...")


# ---------------------------------------------------------------------------
# Student management submenu
# ---------------------------------------------------------------------------

def _student_management_menu(svc, persistence, repos) -> None:
    while True:
        _header("Student Management")
        print("  1. List all students")
        print("  2. Add a student")
        print("  3. Edit a student")
        print("  4. Delete a student")
        print("  0. Back\n")

        choice = input("  Select option: ").strip()

        if choice == "1":
            _header("All Students")
            students = svc.list_students()
            if not students:
                print("  (no students registered)")
            for s in students:
                print(_fmt_student(s))
                print()

        elif choice == "2":
            _header("Add Student")
            sid     = input("  Student ID  (e.g. S004): ").strip()
            name    = input("  Full name: ").strip()
            program = input("  Program: ").strip()

            if not sid or not name or not program:
                print("\n  x ID, name, and program are all required.")
                input("\n  Press Enter to continue...")
                continue

            result = svc.add_student(sid, name, program)
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                print(f"\n  + {result.message}")
                print(_fmt_student(result.student))
                persistence.save(repos)

        elif choice == "3":
            _header("Edit Student")
            for s in svc.list_students():
                print(_fmt_student(s))
                print()

            sid = input("  Student ID to edit: ").strip()
            existing = svc.get_student(sid)
            if isinstance(existing, ErrorDTO):
                print(f"\n  x {existing.message}")
                input("\n  Press Enter to continue...")
                continue

            print(f"\n  Current values for {sid}:")
            print(_fmt_student(existing))
            print("\n  Press Enter on any field to leave it unchanged.\n")

            new_name    = input(f"  New name [{existing.name}]: ").strip()
            new_program = input(f"  New program [{existing.program}]: ").strip()

            parsed_name    = new_name    if new_name    else None
            parsed_program = new_program if new_program else None

            if parsed_name is None and parsed_program is None:
                print("  No changes entered.")
                input("\n  Press Enter to continue...")
                continue

            result = svc.update_student(sid, new_name=parsed_name, new_program=parsed_program)
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                print(f"\n  + {result.message}")
                print(_fmt_student(result.student))
                persistence.save(repos)

        elif choice == "4":
            _header("Delete Student")
            for s in svc.list_students():
                print(_fmt_student(s))
                print()

            sid = input("  Student ID to delete: ").strip()
            existing = svc.get_student(sid)
            if isinstance(existing, ErrorDTO):
                print(f"\n  x {existing.message}")
                input("\n  Press Enter to continue...")
                continue

            print(f"\n  About to delete:")
            print(_fmt_student(existing))
            confirm = input("\n  Type YES to confirm: ").strip()

            if confirm != "YES":
                print("  Deletion cancelled.")
            else:
                result = svc.delete_student(sid)
                if isinstance(result, ErrorDTO):
                    print(f"\n  x {result.message}")
                else:
                    print(f"\n  + {result.message}")
                    persistence.save(repos)

        elif choice == "0":
            break
        else:
            print("  Invalid option.")

        input("\n  Press Enter to continue...")


# ---------------------------------------------------------------------------
# Instructor management submenu
# ---------------------------------------------------------------------------

def _instructor_management_menu(svc, persistence, repos) -> None:
    while True:
        _header("Instructor Management")
        print("  1. List all instructors")
        print("  2. Add an instructor")
        print("  3. Edit an instructor")
        print("  4. Delete an instructor")
        print("  0. Back\n")

        choice = input("  Select option: ").strip()

        if choice == "1":
            _header("All Instructors")
            instructors = svc.list_instructors()
            if not instructors:
                print("  (no instructors on record)")
            for i in instructors:
                print(_fmt_instructor(i))
                print()

        elif choice == "2":
            _header("Add Instructor")
            iid        = input("  Instructor ID  (e.g. I003): ").strip()
            name       = input("  Full name: ").strip()
            department = input("  Department: ").strip()

            if not iid or not name or not department:
                print("\n  x ID, name, and department are all required.")
                input("\n  Press Enter to continue...")
                continue

            result = svc.add_instructor(iid, name, department)
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                print(f"\n  + {result.message}")
                print(_fmt_instructor(result.instructor))
                persistence.save(repos)

        elif choice == "3":
            _header("Edit Instructor")
            for i in svc.list_instructors():
                print(_fmt_instructor(i))
                print()

            iid = input("  Instructor ID to edit: ").strip()
            existing = svc.get_instructor(iid)
            if isinstance(existing, ErrorDTO):
                print(f"\n  x {existing.message}")
                input("\n  Press Enter to continue...")
                continue

            print(f"\n  Current values for {iid}:")
            print(_fmt_instructor(existing))
            print("\n  Press Enter on any field to leave it unchanged.\n")

            new_name = input(f"  New name [{existing.name}]: ").strip()
            new_dept = input(f"  New department [{existing.department}]: ").strip()

            parsed_name = new_name if new_name else None
            parsed_dept = new_dept if new_dept else None

            if parsed_name is None and parsed_dept is None:
                print("  No changes entered.")
                input("\n  Press Enter to continue...")
                continue

            result = svc.update_instructor(iid, new_name=parsed_name, new_department=parsed_dept)
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                print(f"\n  + {result.message}")
                print(_fmt_instructor(result.instructor))
                persistence.save(repos)

        elif choice == "4":
            _header("Delete Instructor")
            for i in svc.list_instructors():
                print(_fmt_instructor(i))
                print()

            iid = input("  Instructor ID to delete: ").strip()
            existing = svc.get_instructor(iid)
            if isinstance(existing, ErrorDTO):
                print(f"\n  x {existing.message}")
                input("\n  Press Enter to continue...")
                continue

            print(f"\n  About to delete:")
            print(_fmt_instructor(existing))
            confirm = input("\n  Type YES to confirm: ").strip()

            if confirm != "YES":
                print("  Deletion cancelled.")
            else:
                result = svc.delete_instructor(iid)
                if isinstance(result, ErrorDTO):
                    print(f"\n  x {result.message}")
                else:
                    print(f"\n  + {result.message}")
                    persistence.save(repos)

        elif choice == "0":
            break
        else:
            print("  Invalid option.")

        input("\n  Press Enter to continue...")


# ---------------------------------------------------------------------------
# Offering management submenu
# ---------------------------------------------------------------------------

def _offering_management_menu(svc, persistence, repos, semester) -> None:
    while True:
        _header("Offering Management")
        print("  1. List all offerings")
        print("  2. Create an offering")
        print("  3. Edit an offering  (capacity / schedule — SCHEDULED only)")
        print("  4. Open an offering  (SCHEDULED → OPEN)")
        print("  5. Close an offering (OPEN → CLOSED)")
        print("  6. Delete an offering")
        print("  0. Back\n")

        choice = input("  Select option: ").strip()

        if choice == "1":
            _header("All Offerings")
            offerings = svc.list_offerings()
            if not offerings:
                print("  (no offerings)")
            for o in offerings:
                print(_fmt_offering(o))
                print()

        elif choice == "2":
            _header("Create Offering")

            # Show available courses and instructors as a quick reference.
            print("  Available courses:")
            for c in svc.list_courses():
                print(f"    [{c.course_code}] {c.title}")
            print()
            print("  Available instructors:")
            for i in svc.list_instructors():
                print(f"    [{i.instructor_id}] {i.name}")
            print()

            oid          = input("  New offering ID  (e.g. OFF004): ").strip()
            course_code  = input("  Course code: ").strip().upper()
            instructor_id = input("  Instructor ID: ").strip()
            capacity_raw = input("  Capacity (integer): ").strip()
            sched_raw    = input(
                "  Schedule (e.g. Monday 08:00-09:30, Wednesday 08:00-09:30)\n"
                "  or blank for TBD: "
            ).strip()

            if not oid or not course_code or not instructor_id:
                print("\n  x Offering ID, course code, and instructor ID are required.")
                input("\n  Press Enter to continue...")
                continue

            try:
                capacity = int(capacity_raw)
            except ValueError:
                print("\n  x Capacity must be a whole number.")
                input("\n  Press Enter to continue...")
                continue

            slots, err = _parse_schedule(sched_raw)
            if err:
                print(f"\n  x {err}")
                input("\n  Press Enter to continue...")
                continue

            result = svc.create_offering(
                oid, course_code, instructor_id, semester, capacity, slots
            )
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                print(f"\n  + {result.message}")
                print(_fmt_offering(result.offering))
                persistence.save(repos)

        elif choice == "3":
            _header("Edit Offering")
            print("  Note: only SCHEDULED offerings can be edited.\n")
            for o in svc.list_offerings():
                print(_fmt_offering(o))
                print()

            oid = input("  Offering ID to edit: ").strip()
            existing = svc.get_offering(oid)
            if isinstance(existing, ErrorDTO):
                print(f"\n  x {existing.message}")
                input("\n  Press Enter to continue...")
                continue

            print(f"\n  Current values for {oid}:")
            print(_fmt_offering(existing))
            print("\n  Press Enter on any field to leave it unchanged.\n")

            capacity_raw = input(f"  New capacity [{existing.capacity}]: ").strip()
            current_sched = ", ".join(
                f"{s.day} {s.start_time}-{s.end_time}" for s in existing.schedule
            ) or "TBD"
            sched_raw = input(
                f"  New schedule [{current_sched}]\n"
                "  (e.g. Monday 08:00-09:30, Wednesday 08:00-09:30 or CLEAR): "
            ).strip()

            parsed_capacity = None
            if capacity_raw:
                try:
                    parsed_capacity = int(capacity_raw)
                except ValueError:
                    print("\n  x Capacity must be a whole number.")
                    input("\n  Press Enter to continue...")
                    continue

            parsed_schedule = None
            if sched_raw.upper() == "CLEAR":
                parsed_schedule = []
            elif sched_raw:
                parsed_schedule, err = _parse_schedule(sched_raw)
                if err:
                    print(f"\n  x {err}")
                    input("\n  Press Enter to continue...")
                    continue

            if parsed_capacity is None and parsed_schedule is None:
                print("  No changes entered.")
                input("\n  Press Enter to continue...")
                continue

            result = svc.update_offering(oid, new_capacity=parsed_capacity, new_schedule=parsed_schedule)
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                print(f"\n  + {result.message}")
                print(_fmt_offering(result.offering))
                persistence.save(repos)

        elif choice == "4":
            _header("Open Offering")
            for o in svc.list_offerings():
                print(_fmt_offering(o))
                print()

            oid = input("  Offering ID to open: ").strip()
            result = svc.open_offering(oid)
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                print(f"\n  + Offering '{oid}' is now OPEN.")
                persistence.save(repos)

        elif choice == "5":
            _header("Close Offering")
            for o in svc.list_offerings():
                print(_fmt_offering(o))
                print()

            oid = input("  Offering ID to close: ").strip()
            result = svc.close_offering(oid)
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                print(f"\n  + Offering '{oid}' is now CLOSED.")
                persistence.save(repos)

        elif choice == "6":
            _header("Delete Offering")
            for o in svc.list_offerings():
                print(_fmt_offering(o))
                print()

            oid = input("  Offering ID to delete: ").strip()
            existing = svc.get_offering(oid)
            if isinstance(existing, ErrorDTO):
                print(f"\n  x {existing.message}")
                input("\n  Press Enter to continue...")
                continue

            print(f"\n  About to delete:")
            print(_fmt_offering(existing))
            confirm = input("\n  Type YES to confirm: ").strip()

            if confirm != "YES":
                print("  Deletion cancelled.")
            else:
                result = svc.delete_offering(oid)
                if isinstance(result, ErrorDTO):
                    print(f"\n  x {result.message}")
                else:
                    print(f"\n  + {result.message}")
                    persistence.save(repos)

        elif choice == "0":
            break
        else:
            print("  Invalid option.")

        input("\n  Press Enter to continue...")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the CLI.  Wire up the app, seed if needed, then loop."""
    svc, persistence, repos, semester = create_app(
        event_handlers=[_cli_event_handler]
    )

    if not svc.list_students():
        seed_demo_data(svc, semester)
        persistence.save(repos)
        print("Demo data loaded.\n")

    while True:
        _header("University Course Registration System")
        print("  1.  View course offerings")
        print("  2.  View students")
        print("  3.  Enroll a student")
        print("  4.  Drop a student")
        print("  5.  View student schedule")
        print("  6.  Search courses")
        print("  7.  Mark course completed")
        print("  8.  Course management     (add / edit / delete)")
        print("  9.  Student management    (add / edit / delete)")
        print("  10. Instructor management (add / edit / delete)")
        print("  11. Offering management   (create / edit / open / close / delete)")
        print("  0.  Exit\n")

        choice = input("  Select option: ").strip()

        if choice == "1":
            _header("Course Offerings - Spring 2026")
            for o in svc.list_offerings(semester):
                print(_fmt_offering(o))
                print()

        elif choice == "2":
            _header("Registered Students")
            for s in svc.list_students():
                print(_fmt_student(s))
                print()

        elif choice == "3":
            _header("Enroll Student")
            sid    = input("  Student ID: ").strip()
            oid    = input("  Offering ID: ").strip()
            result = svc.enroll_student(sid, oid)
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                icon = "!" if result.waitlisted else "+"
                print(f"\n  {icon} {result.message}")
                persistence.save(repos)

        elif choice == "4":
            _header("Drop Student")
            sid    = input("  Student ID: ").strip()
            oid    = input("  Offering ID: ").strip()
            result = svc.drop_student(sid, oid)
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                print(f"\n  + {result.message}")
                persistence.save(repos)

        elif choice == "5":
            _header("Student Schedule")
            sid    = input("  Student ID: ").strip()
            result = svc.get_student_schedule(sid)
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            elif not result:
                print("  Not enrolled in any courses.")
            else:
                for o in result:
                    print(_fmt_offering(o))
                    print()

        elif choice == "6":
            _header("Search Courses")
            kw = input("  Keyword: ").strip()
            results = svc.search_courses(kw)
            if not results:
                print("  No courses found.")
            for c in results:
                print(_fmt_course(c))
                print()

        elif choice == "7":
            _header("Mark Course Completed")
            sid    = input("  Student ID: ").strip()
            code   = input("  Course Code: ").strip()
            result = svc.mark_student_completed(sid, code)
            if isinstance(result, ErrorDTO):
                print(f"\n  x {result.message}")
            else:
                print(f"  + Marked {code} as completed for {sid}.")
                persistence.save(repos)

        elif choice == "8":
            _course_management_menu(svc, persistence, repos)
            continue

        elif choice == "9":
            _student_management_menu(svc, persistence, repos)
            continue

        elif choice == "10":
            _instructor_management_menu(svc, persistence, repos)
            continue

        elif choice == "11":
            _offering_management_menu(svc, persistence, repos, semester)
            continue

        elif choice == "0":
            print("\n  Goodbye!\n")
            break
        else:
            print("  Invalid option.")

        input("\n  Press Enter to continue...")


if __name__ == "__main__":
    main()