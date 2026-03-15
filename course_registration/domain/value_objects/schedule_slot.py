"""
schedule_slot.py — ScheduleSlot value object.

A ScheduleSlot describes a specific day-of-week and time window during
which a CourseOffering meets.  It is a Value Object: immutable, with no
identity of its own.

The key business behaviour it carries is overlaps_with(), which is used
by the RegistrationService to detect schedule conflicts before enrollment.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduleSlot:
    """
    A single class meeting: one day of the week plus a start and end time.

    Fields
    ------
    day        : day of the week, e.g. "Monday"
    start_time : 24-hour HH:MM string, e.g. "08:00"
    end_time   : 24-hour HH:MM string, e.g. "09:30"
    """
    day        : str
    start_time : str
    end_time   : str

    def overlaps_with(self, other: "ScheduleSlot") -> bool:
        """
        Return True when this slot and another occupy the same day and their
        time ranges intersect.

        Two slots overlap when one starts before the other ends AND the other
        starts before the first ends — a standard interval-overlap check.
        String comparison works correctly here because times are in HH:MM
        zero-padded 24-hour format.
        """
        if self.day != other.day:
            return False
        return self.start_time < other.end_time and other.start_time < self.end_time

    def __str__(self) -> str:
        return f"{self.day} {self.start_time}–{self.end_time}"
