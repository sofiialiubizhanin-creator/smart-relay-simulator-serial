"""Allows `python -m relay_host ...` (used by the E2E host fixture, D6)."""
import sys

from .cli import main

sys.exit(main())
