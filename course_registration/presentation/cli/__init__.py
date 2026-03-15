"""
presentation/cli/__init__.py — CLI presentation layer.

The CLI has exactly three responsibilities:
  1. Call bootstrap.create_app() to receive a fully wired service.
  2. Collect raw input from the user via input().
  3. Format the DTOs returned by the service for display on the terminal.

It contains ZERO business logic and ZERO domain imports.

A future GUI module (presentation/gui/__init__.py) will have the same
three responsibilities using widgets instead of input() and print().
Both frontends call the same service methods and receive the same DTOs —
no changes are required in the domain, application, or infrastructure layers.

Course management
-----------------
Option 8 in the main menu opens a Course Management submenu with three
actions: Add Course, Edit Course, and Delete Course.  All three call the
corresponding service methods and display the returned DTO or ErrorDTO.
"""

from __future__ import annotations
import os
import sys

# Allow running this file directly from the presentation/cli directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from course_registration.domain.events    import DomainEvent
from course_registration.application.dtos import (
    OfferingDTO, StudentDTO, CourseDTO,
    CourseManagementResultDTO, EnrollmentResultDTO, ErrorDTO,
)
from course_registration.bootstrap import create_app, seed_demo_data


# ---------------------------------------------------------------------------
# Event handler — CLI-specific
# ---------------------------------------------------------------------------
# The GUI will register its own handler (e.g. append to a log panel) without
# touching this function or the application service.

def _cli_event_handler(event: DomainEvent) -> None:
    """Print a one-line log entry for every domain event that fires."""
    name = event.__class__.__name__
    # Enrollment events carry student_id; course events do not.
    if hasattr(event, "student_id"):
        print(f"  [EVENT] {name}: student={event.student_id}, course={event.course_code}")
    else:
        print(f"  [EVENT] {name}: course={event.course_code}")


# ---------------------------------------------------------------------------
# DTO formatters — CLI-specific
# ---------------------------------------------------------------------------
# These functions know how to render DTOs as terminal text.
# A GUI would have equivalent functions that construct widgets.

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

def _header(title: str) -> None:
    print(f"\n{chr(9472)*55}\n  {title}\n{chr(9472)*55}")


# ---------------------------------------------------------------------------
# Course management submenu
# ---------------------------------------------------------------------------

def _course_management_menu(svc, persistence, repos) -> None:
    """
    Submenu for adding, editing, and deleting courses.

    Each action calls the corresponding service method and displays the
    returned CourseManagementResultDTO or ErrorDTO.  No business logic
    lives here — only input collection and output formatting.
    """
    while True:
        _header("Course Management")
        print("  1. List all courses")
        print("  2. Add a course")
        print("  3. Edit a course")
        print("  4. Delete a course")
        print("  0. Back to main menu\n")

        choice = input("  Select option: ").strip()

        if choice == "1":
            # ── List ──────────────────────────────────────────────────
            _header("Course Catalogue")
            courses = svc.list_courses()
            if not courses:
                print("  (no courses in the catalogue)")
            for c in courses:
                print(_fmt_course(c))
                print()

        elif choice == "2":
            # ── Add ───────────────────────────────────────────────────
            _header("Add Course")
            code    = input("  Course code  (e.g. CS401): ").strip().upper()
            title   = input("  Title: ").strip()
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
            # ── Edit ──────────────────────────────────────────────────
            _header("Edit Course")

            # Show current courses to help the user pick one
            for c in svc.list_courses():
                print(_fmt_course(c))
                print()

            code = input("  Course code to edit: ").strip().upper()

            # Fetch and display the current values so the user knows what to change
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
                "(comma-separated, or CLEAR to remove all): "
            ).strip()

            # None means "leave unchanged"; parse only when the user typed something
            parsed_title   = new_title   if new_title   else None
            parsed_credits = None
            if credits_raw:
                try:
                    parsed_credits = int(credits_raw)
                except ValueError:
                    print("\n  x Credits must be a whole number.")
                    input("\n  Press Enter to continue...")
                    continue

            # Prerequisite handling:
            #   blank         → None (no change)
            #   "CLEAR"       → [] (remove all)
            #   "CS101,CS201" → ["CS101", "CS201"] (replace list)
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
            # ── Delete ────────────────────────────────────────────────
            _header("Delete Course")

            for c in svc.list_courses():
                print(_fmt_course(c))
                print()

            code = input("  Course code to delete: ").strip().upper()

            # Show what will be deleted and ask for confirmation
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
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the CLI.  Wire up the app, seed if needed, then loop."""
    svc, persistence, repos, semester = create_app(
        event_handlers=[_cli_event_handler]
    )

    # Seed demo data on first run (data file does not exist yet).
    if not svc.list_students():
        seed_demo_data(svc, semester)
        persistence.save(repos)
        print("Demo data loaded.\n")

    while True:
        _header("University Course Registration System")
        print("  1. View course offerings")
        print("  2. View students")
        print("  3. Enroll a student")
        print("  4. Drop a student")
        print("  5. View student schedule")
        print("  6. Search courses")
        print("  7. Mark course completed")
        print("  8. Course management  (add / edit / delete)")
        print("  0. Exit\n")

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
            sid    = input("  Student ID  (S001 / S002 / S003): ").strip()
            oid    = input("  Offering ID (OFF001 / OFF002 / OFF003): ").strip()
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
            # Delegate entirely to the course management submenu.
            _course_management_menu(svc, persistence, repos)
            continue  # skip the "press enter" prompt — submenu has its own

        elif choice == "0":
            print("\n  Goodbye!\n")
            break
        else:
            print("  Invalid option.")

        input("\n  Press Enter to continue...")


if __name__ == "__main__":
    main()
