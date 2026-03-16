"""
main.py — Application entry point.
"""

import sys

if "--gui" in sys.argv:
    from course_registration.presentation.gui import main
    main()
else:
    from course_registration.presentation.cli import main
    main()
