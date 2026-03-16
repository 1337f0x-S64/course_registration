# University Course Registration System

A Python desktop app for managing course registrations. Individual can enroll in or drop offerings, prerequisites and credit limits are enforced, and a waitlist automatically promotes students when a seat opens up.

## How to run
```bash
python main.py --gui   # desktop interface (recommended)
python main.py         # terminal interface

## Structure
course_registration/
├── domain/               # All business rules live here
│   ├── entities/         # Course, Student, Instructor
│   ├── aggregates/       # CourseOffering — the enrollment boundary
│   ├── value_objects/    # Semester, ScheduleSlot, status enums
│   ├── events/           # StudentEnrolled, CourseCreated, etc.
│   ├── repositories/     # Abstract interfaces (no storage code)
│   └── services/         # RegistrationService (cross-aggregate logic)
├── application/
│   ├── services/         # RegistrationAppService — orchestrates use cases
│   └── dtos/             # Read-only snapshots returned to the UI
├── infrastructure/
│   ├── repositories/     # In-memory implementations
│   └── persistence/      # JSON file save/load
├── presentation/
│   ├── cli/              # Terminal interface
│   └── gui/              # Tkinter desktop interface
└── bootstrap/            # Wires everything together, seeds demo data

##**DDD in this Project**
Entities vs Value Objects A Student has an identity S001; two students with the same name are still different people. A ScheduleSlot has no identity; two slots with the same day and time are the same. Entities live in domain/entities/, value objects in domain/value_objects/.

Aggregates CourseOffering is the Aggregate Root. It owns the enrolled list and waitlist. All enrollment changes go through enroll_student() and drop_student(), which enforce the rules: offering must be OPEN, prerequisites must be met, credit limit cannot be exceeded, and waitlist promotion happens automatically on drop.

Domain Services RegistrationService handles schedule conflict detection across multiple offerings. This logic cannot live inside a single aggregate, so the service applies the rule and delegates back to aggregates.

Repositories Domain defines what a repository does; infrastructure defines how. Currently in-memory dicts backed by JSON. Swapping in a database later would not touch domain or application layers.

Application Service RegistrationAppService orchestrates flows: loads data, calls domain logic, saves, publishes events. No business decisions happen here. Always returns DTOs, never raw domain objects.

Domain Events When something meaningful happens, such as enrollment, drop, or waitlist promotion, the aggregate records an event. The application service publishes it after saving. Events are named in past tense because they describe facts, not commands.

##**Demo data**
5 courses CS101 → CS201 → CS301, MATH101 → MATH201
2 instructors, 3 students, 3 open offerings
Pablo has already completed CS101 so he can enroll in CS201

