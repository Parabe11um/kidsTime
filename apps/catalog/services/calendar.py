"""Downloadable iCalendar events for confirmed, upcoming sessions (RFC 5545)."""

from datetime import timezone
from urllib.parse import urlsplit


def _text(value):
    return str(value).replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def _fold(line):
    # The limit is 75 UTF-8 octets, including the continuation's leading space.
    lines, current, size = [], "", 0
    for character in line:
        length = len(character.encode("utf-8"))
        if size + length > 75:
            lines.append(current)
            current, size = " ", 1
        current += character
        size += length
    lines.append(current)
    return "\r\n".join(lines)


def build_event_calendar(event, session, url, now):
    def utc(value):
        return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//KidsTime//Events//RU",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT",
        f"UID:event-{event.pk}-session-{session.pk}@{urlsplit(url).hostname}",
        f"DTSTAMP:{utc(now)}", f"DTSTART:{utc(session.starts_at)}",
    ]
    if session.ends_at and session.ends_at > session.starts_at:
        lines.append(f"DTEND:{utc(session.ends_at)}")
    elif event.duration_minutes:
        lines.append(f"DURATION:PT{event.duration_minutes}M")
    lines.extend([
        f"SUMMARY:{_text(event.title)}",
        f"LOCATION:{_text(event.venue.name + ', ' + event.venue.address)}",
        f"DESCRIPTION:{_text(event.short_description)}",
        f"URL:{url}", "END:VEVENT", "END:VCALENDAR",
    ])
    return ("\r\n".join(_fold(line) for line in lines) + "\r\n").encode("utf-8")
