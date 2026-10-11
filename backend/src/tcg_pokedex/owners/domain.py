"""The single household owner that every user-owned record belongs to in the MVP.

Seeded by the first migration. The id never changes, so later slices can scope
records to it before profiles exist.
"""

from uuid import UUID

HOUSEHOLD_OWNER_ID = UUID("9fb0c458-5ccf-477a-945e-276438b0f310")
HOUSEHOLD_OWNER_NAME = "Casa"
