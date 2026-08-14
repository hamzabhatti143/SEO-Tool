"""SQLAlchemy ORM models.

Importing them here ensures they are registered on ``Base.metadata``
so ``create_all`` / Alembic can see them.
"""

from app.models.agency import (
    ClientShareLink,
    ProjectInvite,
    ProjectMember,
)
from app.models.audit import AuditReport
from app.models.automation import AutomationSettings
from app.models.content import Content
from app.models.keyword import Keyword
from app.models.page import ProjectPage
from app.models.project import Project
from app.models.rank_tracking import RankSnapshot, TrackedKeyword
from app.models.subscription import Subscription
from app.models.user import User

__all__ = [
    "User",
    "Project",
    "AuditReport",
    "Keyword",
    "Content",
    "Subscription",
    "ProjectPage",
    "TrackedKeyword",
    "RankSnapshot",
    "AutomationSettings",
    "ProjectMember",
    "ProjectInvite",
    "ClientShareLink",
]
