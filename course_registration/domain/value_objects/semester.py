"""
semester.py — Semester value object.

A Semester describes an academic period.  It is a Value Object, meaning:
  - It has no unique identity; two Semesters with identical fields are equal.
  - It is immutable; once created, its fields cannot change.

Python enforces immutability here via @dataclass(frozen=True), which causes
any attempted field assignment to raise a TypeError at runtime.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Semester:
    """
    An academic period during which courses are offered.

    Fields
    ------
    semester_id : unique code used for persistence lookups (e.g. "SEM-2026-SP")
    term        : human-readable period name (e.g. "Spring", "Fall")
    year        : calendar year (e.g. 2026)
    start_date  : first day of the registration window
    end_date    : last day of the registration window
    """
    semester_id : str
    term        : str
    year        : int
    start_date  : date
    end_date    : date

    def is_registration_open(self, on_date: date = None) -> bool:
        """
        Return True when the given date falls inside the semester window.
        If no date is provided, today's date is used.
        """
        check = on_date or date.today()
        return self.start_date <= check <= self.end_date

    def __str__(self) -> str:
        # e.g. "Spring 2026" — used in display strings and DTO labels
        return f"{self.term} {self.year}"
