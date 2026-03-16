"""
presentation/gui/__init__.py — Tkinter GUI presentation layer.

All business logic stays in the application service; this module only
collects input via widgets and displays the DTOs it receives back.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from course_registration.application.dtos import ErrorDTO, OfferingDTO, StudentDTO, CourseDTO
from course_registration.bootstrap import create_app, seed_demo_data


# Palette

BG          = "#F0F4F8"
SURFACE     = "#FFFFFF"
PRIMARY     = "#4F6AF0"
PRIMARY_HOV = "#3A54D4"
DANGER      = "#E05252"
DANGER_HOV  = "#C43C3C"
HEADER_BG   = "#3B4A8A"
HEADER_FG   = "#FFFFFF"
TEXT        = "#1E2A3A"
MUTED       = "#6B7A99"
ROW_ODD     = "#FFFFFF"
ROW_EVEN    = "#EBF0FB"
SELECT_BG   = "#C7D3F7"
SELECT_FG   = "#1E2A3A"
BORDER      = "#D0D8EC"

# Theme bootstrap — call once before any widget is created

def _apply_theme(root: tk.Tk) -> None:
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")

    # General
    style.configure(".",          background=BG,      foreground=TEXT,
                    font=("Segoe UI", 10))
    style.configure("TFrame",     background=BG)
    style.configure("TLabel",     background=BG,      foreground=TEXT,
                    font=("Segoe UI", 10))
    style.configure("TLabelframe",       background=BG,  relief="flat",
                    bordercolor=BORDER)
    style.configure("TLabelframe.Label", background=BG,  foreground=PRIMARY,
                    font=("Segoe UI", 10, "bold"))

    # Notebook
    style.configure("TNotebook",       background=BG,  borderwidth=0)
    style.configure("TNotebook.Tab",   background="#D6DEFA", foreground=MUTED,
                    padding=[14, 6],   font=("Segoe UI", 10))
    style.map("TNotebook.Tab",
              background=[("selected", SURFACE)],
              foreground=[("selected", PRIMARY)],
              font=[("selected", ("Segoe UI", 10, "bold"))])

    # Treeview
    style.configure("Treeview",
                    background=SURFACE, foreground=TEXT,
                    fieldbackground=SURFACE, rowheight=26,
                    borderwidth=0, font=("Segoe UI", 10))
    style.configure("Treeview.Heading",
                    background=PRIMARY, foreground=HEADER_FG,
                    font=("Segoe UI", 10, "bold"), relief="flat")
    style.map("Treeview",
              background=[("selected", SELECT_BG)],
              foreground=[("selected", SELECT_FG)])
    style.map("Treeview.Heading", background=[("active", PRIMARY_HOV)])

    # Scrollbar
    style.configure("Vertical.TScrollbar", background=BORDER,
                    troughcolor=BG, borderwidth=0, arrowsize=12)

    # Entry
    style.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    insertcolor=TEXT, padding=4)
    style.map("TEntry", bordercolor=[("focus", PRIMARY)])

    # Primary button
    style.configure("Primary.TButton",
                    background=PRIMARY, foreground=HEADER_FG,
                    font=("Segoe UI", 10, "bold"),
                    borderwidth=0, focusthickness=0, padding=[12, 6])
    style.map("Primary.TButton",
              background=[("active", PRIMARY_HOV), ("pressed", PRIMARY_HOV)])

    # Danger button
    style.configure("Danger.TButton",
                    background=DANGER, foreground=HEADER_FG,
                    font=("Segoe UI", 10, "bold"),
                    borderwidth=0, focusthickness=0, padding=[12, 6])
    style.map("Danger.TButton",
              background=[("active", DANGER_HOV), ("pressed", DANGER_HOV)])

    # Secondary (neutral) button
    style.configure("Secondary.TButton",
                    background=BORDER, foreground=TEXT,
                    font=("Segoe UI", 10),
                    borderwidth=0, focusthickness=0, padding=[12, 6])
    style.map("Secondary.TButton",
              background=[("active", "#BCC8E0"), ("pressed", "#BCC8E0")])



# Helpers

def _slot_str(offering: OfferingDTO) -> str:
    return ", ".join(str(s) for s in offering.schedule) or "TBD"


def _show_error(msg: str) -> None:
    messagebox.showerror("Error", msg)


def _show_info(msg: str) -> None:
    messagebox.showinfo("Success", msg)

# Reusable table widget


class _Table(ttk.Frame):
    def __init__(self, parent, columns: list[tuple[str, int]], **kw):
        super().__init__(parent, **kw)
        self.configure(style="TFrame")
        self.tree = ttk.Treeview(self, columns=[c for c, _ in columns],
                                 show="headings", selectmode="browse")
        self.tree.tag_configure("odd",  background=ROW_ODD)
        self.tree.tag_configure("even", background=ROW_EVEN)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        for col, width in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._row_count = 0

    def clear(self):
        self.tree.delete(*self.tree.get_children())
        self._row_count = 0

    def insert(self, values: tuple):
        tag = "even" if self._row_count % 2 else "odd"
        self.tree.insert("", "end", values=values, tags=(tag,))
        self._row_count += 1

    def selected_value(self, col_index: int):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])["values"][col_index]



# Tab for the course Offerings

class _OfferingsTab(ttk.Frame):
    COLS = [("ID", 80), ("Course", 80), ("Title", 180), ("Instructor", 140),
            ("Schedule", 200), ("Seats", 70), ("Waitlist", 60), ("Status", 70)]

    def __init__(self, parent, app):
        super().__init__(parent, padding=8)
        self._app = app
        self._table = _Table(self, self.COLS)
        self._table.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self):
        self._table.clear()
        for o in self._app.list_offerings():
            self._table.insert((
                o.offering_id, o.course.course_code, o.course.title,
                o.instructor.name, _slot_str(o),
                f"{o.enrolled_count}/{o.capacity}", o.waitlist_count, o.status,
            ))

# Table for Students

class _StudentsTab(ttk.Frame):
    COLS = [("ID", 70), ("Name", 160), ("Program", 160), ("Completed", 260)]

    def __init__(self, parent, app):
        super().__init__(parent, padding=8)
        self._app = app
        self._table = _Table(self, self.COLS)
        self._table.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self):
        self._table.clear()
        for s in self._app.list_students():
            done = ", ".join(s.completed_courses) or "—"
            self._table.insert((s.student_id, s.name, s.program, done))

# Tab for  Enroll / Drop

class _EnrollTab(ttk.Frame):
    def __init__(self, parent, app, persistence, repos, refresh_cb):
        super().__init__(parent, padding=12)
        self._app = app
        self._persistence = persistence
        self._repos = repos
        self._refresh_cb = refresh_cb

        lf = ttk.LabelFrame(self, text="Enroll / Drop Student", padding=10)
        lf.pack(fill="x", padx=20, pady=10)

        ttk.Label(lf, text="Student ID:").grid(row=0, column=0, sticky="w", pady=3)
        self._sid = ttk.Entry(lf, width=20)
        self._sid.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(lf, text="Offering ID:").grid(row=1, column=0, sticky="w", pady=3)
        self._oid = ttk.Entry(lf, width=20)
        self._oid.grid(row=1, column=1, sticky="w", padx=6)

        btn_frame = ttk.Frame(lf)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=8)
        ttk.Button(btn_frame, text="Enroll", style="Primary.TButton",
                   command=self._enroll).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Drop", style="Danger.TButton",
                   command=self._drop).pack(side="left", padx=6)

        # Quick-reference tables
        ref = ttk.Frame(self)
        ref.pack(fill="both", expand=True, padx=8)

        ttk.Label(ref, text="Students").grid(row=0, column=0, sticky="w")
        ttk.Label(ref, text="Offerings").grid(row=0, column=1, sticky="w", padx=(20, 0))

        self._stbl = _Table(ref, [("ID", 60), ("Name", 140)])
        self._stbl.grid(row=1, column=0, sticky="nsew")

        self._otbl = _Table(ref, [("ID", 70), ("Course", 70), ("Status", 60)])
        self._otbl.grid(row=1, column=1, sticky="nsew", padx=(20, 0))

        ref.columnconfigure(0, weight=1)
        ref.columnconfigure(1, weight=1)
        ref.rowconfigure(1, weight=1)

        self.refresh()

    def refresh(self):
        self._stbl.clear()
        for s in self._app.list_students():
            self._stbl.insert((s.student_id, s.name))
        self._otbl.clear()
        for o in self._app.list_offerings():
            self._otbl.insert((o.offering_id, o.course.course_code, o.status))

    def _enroll(self):
        sid, oid = self._sid.get().strip(), self._oid.get().strip()
        if not sid or not oid:
            _show_error("Please enter both Student ID and Offering ID.")
            return
        result = self._app.enroll_student(sid, oid)
        if isinstance(result, ErrorDTO):
            _show_error(result.message)
        else:
            _show_info(result.message)
            self._persistence.save(self._repos)
            self._refresh_cb()

    def _drop(self):
        sid, oid = self._sid.get().strip(), self._oid.get().strip()
        if not sid or not oid:
            _show_error("Please enter both Student ID and Offering ID.")
            return
        result = self._app.drop_student(sid, oid)
        if isinstance(result, ErrorDTO):
            _show_error(result.message)
        else:
            _show_info(result.message)
            self._persistence.save(self._repos)
            self._refresh_cb()

# Tab fpr Student Schedule

class _ScheduleTab(ttk.Frame):
    COLS = [("Offering", 80), ("Course", 80), ("Title", 180),
            ("Instructor", 140), ("Schedule", 200), ("Status", 70)]

    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self._app = app

        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Student ID:").pack(side="left")
        self._sid = ttk.Entry(top, width=16)
        self._sid.pack(side="left", padx=6)
        ttk.Button(top, text="View Schedule", style="Primary.TButton",
                   command=self._load).pack(side="left")

        self._table = _Table(self, self.COLS)
        self._table.pack(fill="both", expand=True)

    def _load(self):
        sid = self._sid.get().strip()
        if not sid:
            _show_error("Enter a Student ID.")
            return
        result = self._app.get_student_schedule(sid)
        if isinstance(result, ErrorDTO):
            _show_error(result.message)
            return
        self._table.clear()
        if not result:
            messagebox.showinfo("Schedule", "Not enrolled in any courses.")
            return
        for o in result:
            self._table.insert((
                o.offering_id, o.course.course_code, o.course.title,
                o.instructor.name, _slot_str(o), o.status,
            ))

# Tab for Search Courses

class _SearchTab(ttk.Frame):
    COLS = [("Code", 90), ("Title", 220), ("Credits", 60), ("Prerequisites", 200)]

    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self._app = app

        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Course:").pack(side="left")
        self._kw = ttk.Entry(top, width=24)
        self._kw.pack(side="left", padx=6)
        ttk.Button(top, text="Search", style="Primary.TButton",
                   command=self._search).pack(side="left")
        self._kw.bind("<Return>", lambda _: self._search())

        self._table = _Table(self, self.COLS)
        self._table.pack(fill="both", expand=True)

    def _search(self):
        kw = self._kw.get().strip()
        results = self._app.search_courses(kw)
        self._table.clear()
        for c in results:
            prereqs = ", ".join(c.prerequisites) or "—"
            self._table.insert((c.course_code, c.title, c.credits, prereqs))

# Tab for Course Management

class _CourseManagementTab(ttk.Frame):
    COLS = [("Code", 90), ("Title", 220), ("Credits", 60), ("Prerequisites", 200)]

    def __init__(self, parent, app, persistence, repos):
        super().__init__(parent, padding=8)
        self._app = app
        self._persistence = persistence
        self._repos = repos

        self._table = _Table(self, self.COLS)
        self._table.pack(fill="both", expand=True)

        btn_row = ttk.Frame(self)
        btn_row.pack(pady=6)
        ttk.Button(btn_row, text="Add Course",     style="Primary.TButton",
                   command=self._add).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Edit Selected", style="Secondary.TButton",
                   command=self._edit).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Delete Selected", style="Danger.TButton",
                   command=self._delete).pack(side="left", padx=4)

        self.refresh()

    def refresh(self):
        self._table.clear()
        for c in self._app.list_courses():
            prereqs = ", ".join(c.prerequisites) or "—"
            self._table.insert((c.course_code, c.title, c.credits, prereqs))

    # Add a new course

    def _add(self):
        dlg = _CourseDialog(self, title="Add Course")
        if not dlg.result:
            return
        code, title, credits, prereqs = dlg.result
        result = self._app.add_course(code, title, credits, prereqs)
        if isinstance(result, ErrorDTO):
            _show_error(result.message)
        else:
            _show_info(result.message)
            self._persistence.save(self._repos)
            self.refresh()

    # Edit a course

    def _edit(self):
        code = self._table.selected_value(0)
        if not code:
            _show_error("Select a course to edit.")
            return
        existing = self._app.get_course(str(code))
        if isinstance(existing, ErrorDTO):
            _show_error(existing.message)
            return
        dlg = _CourseDialog(self, title="Edit Course", course=existing)
        if not dlg.result:
            return
        _, new_title, new_credits, new_prereqs = dlg.result
        result = self._app.update_course(
            str(code),
            new_title=new_title or None,
            new_credits=new_credits,
            new_prereq_codes=new_prereqs,
        )
        if isinstance(result, ErrorDTO):
            _show_error(result.message)
        else:
            _show_info(result.message)
            self._persistence.save(self._repos)
            self.refresh()

    #delete a course

    def _delete(self):
        code = self._table.selected_value(0)
        if not code:
            _show_error("Select a course to delete.")
            return
        if not messagebox.askyesno("Confirm Delete",
                                   f"Permanently delete course '{code}'?"):
            return
        result = self._app.delete_course(str(code))
        if isinstance(result, ErrorDTO):
            _show_error(result.message)
        else:
            _show_info(result.message)
            self._persistence.save(self._repos)
            self.refresh()

# Course add and edit dialog

class _CourseDialog(tk.Toplevel):
    def __init__(self, parent, title: str, course: CourseDTO = None):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        pad = {"padx": 10, "pady": 5}

        # Header bar
        hdr = tk.Frame(self, bg=HEADER_BG, height=40)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        tk.Label(hdr, text=title, bg=HEADER_BG, fg=HEADER_FG,
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=12, pady=8)

        ttk.Label(self, text="Course Code:").grid(row=1, column=0, sticky="w", **pad)
        self._code = ttk.Entry(self, width=20)
        self._code.grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(self, text="Title:").grid(row=2, column=0, sticky="w", **pad)
        self._title = ttk.Entry(self, width=30)
        self._title.grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(self, text="Credits:").grid(row=3, column=0, sticky="w", **pad)
        self._credits = ttk.Entry(self, width=8)
        self._credits.grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(self, text="Prerequisites\n(comma-separated):").grid(row=4, column=0, sticky="w", **pad)
        self._prereqs = ttk.Entry(self, width=30)
        self._prereqs.grid(row=4, column=1, sticky="w", **pad)

        if course:
            self._code.insert(0, course.course_code)
            self._code.configure(state="disabled")
            self._title.insert(0, course.title)
            self._credits.insert(0, str(course.credits))
            self._prereqs.insert(0, ", ".join(course.prerequisites))

        btn = ttk.Frame(self)
        btn.grid(row=5, column=0, columnspan=2, pady=10)
        ttk.Button(btn, text="Save",   style="Primary.TButton",
                   command=self._save).pack(side="left", padx=6)
        ttk.Button(btn, text="Cancel", style="Secondary.TButton",
                   command=self.destroy).pack(side="left", padx=6)

        self.wait_window()

    def _save(self):
        code    = self._code.get().strip().upper()
        title   = self._title.get().strip()
        credits_raw = self._credits.get().strip()
        prereq_raw  = self._prereqs.get().strip()

        if not code or not title:
            _show_error("Code and Title are required.")
            return
        try:
            credits = int(credits_raw)
        except ValueError:
            _show_error("Credits must be a whole number.")
            return

        prereqs = (
            [p.strip().upper() for p in prereq_raw.split(",") if p.strip()]
            if prereq_raw else []
        )
        self.result = (code, title, credits, prereqs)
        self.destroy()

# Tab for Mark Course Completed

class _MarkCompletedTab(ttk.Frame):
    def __init__(self, parent, app, persistence, repos):
        super().__init__(parent, padding=12)
        self._app = app
        self._persistence = persistence
        self._repos = repos

        lf = ttk.LabelFrame(self, text="Mark Course as Completed", padding=10)
        lf.pack(fill="x", padx=20, pady=10)

        ttk.Label(lf, text="Student ID:").grid(row=0, column=0, sticky="w", pady=3)
        self._sid = ttk.Entry(lf, width=20)
        self._sid.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(lf, text="Course Code:").grid(row=1, column=0, sticky="w", pady=3)
        self._code = ttk.Entry(lf, width=20)
        self._code.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Button(lf, text="Mark Completed", style="Primary.TButton",
                   command=self._mark).grid(row=2, column=0, columnspan=2, pady=8)

        # Quick-reference
        ref = ttk.Frame(self)
        ref.pack(fill="both", expand=True, padx=8)
        ttk.Label(ref, text="Students").grid(row=0, column=0, sticky="w")
        ttk.Label(ref, text="Courses").grid(row=0, column=1, sticky="w", padx=(20, 0))

        self._stbl = _Table(ref, [("ID", 60), ("Name", 140), ("Completed", 200)])
        self._stbl.grid(row=1, column=0, sticky="nsew")

        self._ctbl = _Table(ref, [("Code", 80), ("Title", 200)])
        self._ctbl.grid(row=1, column=1, sticky="nsew", padx=(20, 0))

        ref.columnconfigure(0, weight=1)
        ref.columnconfigure(1, weight=1)
        ref.rowconfigure(1, weight=1)

        self.refresh()

    def refresh(self):
        self._stbl.clear()
        for s in self._app.list_students():
            self._stbl.insert((s.student_id, s.name, ", ".join(s.completed_courses) or "—"))
        self._ctbl.clear()
        for c in self._app.list_courses():
            self._ctbl.insert((c.course_code, c.title))

    def _mark(self):
        sid  = self._sid.get().strip()
        code = self._code.get().strip().upper()
        if not sid or not code:
            _show_error("Enter both Student ID and Course Code.")
            return
        result = self._app.mark_student_completed(sid, code)
        if isinstance(result, ErrorDTO):
            _show_error(result.message)
        else:
            _show_info(f"Marked {code} as completed for {sid}.")
            self._persistence.save(self._repos)
            self.refresh()

# Main application window

class _App(tk.Tk):
    def __init__(self, svc, persistence, repos, semester):
        super().__init__()
        self.title("University Course Registration System")
        self.geometry("900x580")
        self.minsize(720, 440)
        _apply_theme(self)

        # Header banner
        banner = tk.Frame(self, bg=HEADER_BG, height=52)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner, text="University Course Registration System",
                 bg=HEADER_BG, fg=HEADER_FG,
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=16, pady=12)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self._offerings_tab = _OfferingsTab(nb, svc)
        self._students_tab  = _StudentsTab(nb, svc)
        self._enroll_tab    = _EnrollTab(nb, svc, persistence, repos, self._refresh_all)
        self._schedule_tab  = _ScheduleTab(nb, svc)
        self._search_tab    = _SearchTab(nb, svc)
        self._courses_tab   = _CourseManagementTab(nb, svc, persistence, repos)
        self._mark_tab      = _MarkCompletedTab(nb, svc, persistence, repos)

        nb.add(self._offerings_tab, text="  Offerings  ")
        nb.add(self._students_tab,  text="  Students  ")
        nb.add(self._enroll_tab,    text="  Enroll / Drop  ")
        nb.add(self._schedule_tab,  text="  Schedule  ")
        nb.add(self._search_tab,    text="  Search  ")
        nb.add(self._courses_tab,   text="  Courses  ")
        nb.add(self._mark_tab,      text="  Mark Completed  ")

    def _refresh_all(self):
        self._offerings_tab.refresh()
        self._students_tab.refresh()
        self._enroll_tab.refresh()
        self._mark_tab.refresh()


# Entry point
def main() -> None:
    svc, persistence, repos, semester = create_app()

    if not svc.list_students():
        seed_demo_data(svc, semester)
        persistence.save(repos)

    app = _App(svc, persistence, repos, semester)
    app.mainloop()
