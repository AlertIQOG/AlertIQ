"""Flatten domain records into the canonical text that gets embedded.

Each function returns a single string whose first line is a ``[TYPE]`` header
telling the LLM what it is reading. The same strings become the numbered
context blocks the model cites from in Phase 4, so keep them readable.
"""

from app.models.alert import Alert
from app.models.incident import Incident
from app.models.note import Note


def flatten_alert(alert: Alert, notes: list[Note]) -> str:
    """Canonical text for a resolved alert: message + key labels + its notes."""
    lines: list[str] = ["[ALERT]", f"Message: {alert.message}"]

    labelled = [
        ("Application", alert.application),
        ("Component", alert.component),
        ("Region", alert.region),
        ("Severity", alert.severity.value if alert.severity else None),
        ("Impact", alert.impact),
    ]
    lines += [f"{label}: {value}" for label, value in labelled if value]

    if notes:
        lines.append("Resolution notes:")
        lines += [f"- {note.content}" for note in notes]

    return "\n".join(lines)


def flatten_incident(incident: Incident) -> str:
    """Canonical text for an incident: title + priority + services + notes."""
    lines: list[str] = ["[INCIDENT]", f"Title: {incident.title}"]

    if incident.priority:
        lines.append(f"Priority: {incident.priority.value}")
    if incident.affected_services:
        lines.append(f"Affected services: {', '.join(incident.affected_services)}")
    if incident.notes:
        lines.append(f"Notes: {incident.notes}")

    return "\n".join(lines)
