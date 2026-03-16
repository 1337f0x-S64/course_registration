"""
main.py — Application entry point.

Run the CLI:
    python main.py

Run the GUI (once presentation/gui/ is implemented):
    python main.py --gui
"""

import sys

if "--gui" in sys.argv:
    from course_registration.presentation.gui import main
    main()
else:
    from course_registration.presentation.cli import main
    main()
