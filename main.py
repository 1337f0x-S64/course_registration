"""
main.py — Application entry point.

Run the CLI:
    python main.py

Run the GUI (once presentation/gui/ is implemented):
    python main.py --gui
"""

import sys

if "--gui" in sys.argv:
    # ----------------------------------------------------------------
    # Future GUI entry point.
    # Uncomment and implement when presentation/gui/__init__.py exists:
    #
    #   from course_registration.presentation.gui import main
    #   main()
    # ----------------------------------------------------------------
    print("GUI not yet implemented. Run without --gui to use the CLI.")
else:
    from course_registration.presentation.cli import main
    main()
