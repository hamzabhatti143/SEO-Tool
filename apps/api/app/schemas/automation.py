"""Pydantic schemas for the Automation module."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class AutomationSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    weekly_audit: bool
    broken_link_monitoring: bool
    competitor_monitoring: bool
    email_notifications: bool
    notify_rank_drops: bool
    notify_broken_links: bool
    weekly_summary: bool
    audit_url: str | None = None
    monitor_url: str | None = None
    competitor_urls: list[str] | None = None
    notification_email: str | None = None


class AutomationSettingsUpdate(BaseModel):
    weekly_audit: bool | None = None
    broken_link_monitoring: bool | None = None
    competitor_monitoring: bool | None = None
    email_notifications: bool | None = None
    notify_rank_drops: bool | None = None
    notify_broken_links: bool | None = None
    weekly_summary: bool | None = None
    audit_url: str | None = Field(default=None, max_length=2048)
    monitor_url: str | None = Field(default=None, max_length=2048)
    competitor_urls: list[str] | None = None
    notification_email: str | None = Field(default=None, max_length=320)
