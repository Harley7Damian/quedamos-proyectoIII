"""Lectura de un archivo de calendario (.ics, RFC 5545) para calcular horarios libres (TR-14).

Es el plan alterno a Google Calendar: el archivo se lee en memoria, se calculan los intervalos ocupados
de la semana de la solicitud y se descarta. No se guarda el archivo ni el titulo, la descripcion, los
asistentes o la ubicacion de ningun evento: solo queda la disponibilidad resultante.

Se interpretan eventos con hora, de dia completo, con duracion, con zona horaria, cancelados, libres
(TRANSP:TRANSPARENT), recurrentes (diarios, semanales, mensuales por dia del mes y anuales) con sus
fechas excluidas y las instancias modificadas. Lo que no se puede interpretar se cuenta y se informa.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from scheduling.matching import AVAILABLE, HOURS, block_key

MAX_BYTES = 1024 * 1024  # 1 MB
MAX_EVENTS = 5000
MAX_STEPS = 50000  # tope de iteraciones al expandir una recurrencia
MAX_TOTAL_STEPS = 300000  # tope de iteraciones de todo el archivo, para que un archivo malicioso no consuma el servicio

WINDOWS_ZONES = {
    "SA Pacific Standard Time": "America/Lima",
    "Pacific Standard Time": "America/Los_Angeles",
    "Mountain Standard Time": "America/Denver",
    "Central Standard Time": "America/Chicago",
    "Eastern Standard Time": "America/New_York",
    "SA Eastern Standard Time": "America/Sao_Paulo",
    "Argentina Standard Time": "America/Argentina/Buenos_Aires",
    "Romance Standard Time": "Europe/Paris",
    "W. Europe Standard Time": "Europe/Berlin",
    "GMT Standard Time": "Europe/London",
    "UTC": "UTC",
}
WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
SUPPORTED_RULE_KEYS = {"FREQ", "INTERVAL", "COUNT", "UNTIL", "BYDAY", "BYMONTHDAY", "WKST"}
_DURATION = re.compile(r"^([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


class ICSError(ValueError):
    """El archivo no se puede usar. El mensaje se muestra tal cual a la persona."""


class _BadEvent(ValueError):
    pass


class _Unsupported(ValueError):
    pass


@dataclass
class ImportResult:
    busy: list = field(default_factory=list)  # [(inicio, fin)] con zona horaria, solo lo que toca la semana
    events: int = 0  # eventos leidos
    skipped: int = 0  # eventos con datos que no se pudieron leer
    unsupported: int = 0  # recurrencias que no se pudieron interpretar
    unknown_zones: set = field(default_factory=set)
    steps: int = 0  # iteraciones gastadas al expandir recurrencias


# ------------------------------------------------------------------ lectura del texto


def decode_ics(raw: bytes) -> str:
    """Valida el tamano y devuelve el texto del archivo. Rechaza archivos vacios, enormes o binarios."""
    if not raw or not raw.strip():
        raise ICSError("El archivo está vacío.")
    if len(raw) > MAX_BYTES:
        raise ICSError(f"El archivo supera el máximo de {MAX_BYTES // (1024 * 1024)} MB. Exporta solo los próximos meses.")
    if b"\x00" in raw:
        raise ICSError("El archivo no es un calendario de texto (.ics).")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ICSError("No pudimos leer el texto del archivo.")


def _unfold(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n[ \t]", "", text)
    return [line for line in text.split("\n") if line.strip()]


def _split_outside_quotes(text: str, separator: str) -> list[str]:
    parts, current, quoted = [], "", False
    for char in text:
        if char == '"':
            quoted = not quoted
        if char == separator and not quoted:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    return parts


def _parse_line(line: str):
    quoted = False
    for index, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char == ":" and not quoted:
            head, value = line[:index], line[index + 1:]
            break
    else:
        return None
    pieces = _split_outside_quotes(head, ";")
    params = {}
    for piece in pieces[1:]:
        key, _, val = piece.partition("=")
        params[key.upper()] = val.strip('"')
    return pieces[0].upper(), params, value


def _collect_events(lines: list[str]) -> list[dict]:
    """Devuelve una lista de eventos, cada uno {NOMBRE: [(parametros, valor)]}. Ignora alarmas y zonas horarias."""
    events, stack = [], []
    for line in lines:
        parsed = _parse_line(line)
        if parsed is None:
            continue
        name, params, value = parsed
        if name == "BEGIN":
            stack.append(value.strip().upper())
            if stack[-1] == "VEVENT":
                events.append({})
        elif name == "END":
            if stack:
                stack.pop()
        elif stack and stack[-1] == "VEVENT":
            events[-1].setdefault(name, []).append((params, value))
    return events


# ------------------------------------------------------------------ fechas y duraciones


def _zone(tzid, default_tz, result):
    if not tzid:
        return default_tz
    for candidate in (tzid, WINDOWS_ZONES.get(tzid)):
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    result.unknown_zones.add(tzid)
    return default_tz


def _parse_dt(value, params, default_tz, result):
    """Devuelve (datetime con zona horaria, es_dia_completo)."""
    value = value.strip()
    try:
        if params.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", value):
            day = datetime.strptime(value[:8], "%Y%m%d").date()
            return datetime.combine(day, time.min, tzinfo=default_tz), True
        if value.endswith(("Z", "z")):
            return datetime.strptime(value[:-1], "%Y%m%dT%H%M%S").replace(tzinfo=dt_timezone.utc), False
        naive = datetime.strptime(value, "%Y%m%dT%H%M%S")
    except ValueError as exc:
        raise _BadEvent(str(exc)) from exc
    return naive.replace(tzinfo=_zone(params.get("TZID"), default_tz, result)), False


def _parse_duration(value):
    match = _DURATION.match(value.strip())
    if not match or not any(match.groups()[1:]):
        raise _BadEvent("duracion invalida")
    sign, weeks, days, hours, minutes, seconds = match.groups()
    delta = timedelta(weeks=int(weeks or 0), days=int(days or 0), hours=int(hours or 0),
                      minutes=int(minutes or 0), seconds=int(seconds or 0))
    return -delta if sign == "-" else delta


def _first(event, name):
    values = event.get(name)
    return values[0] if values else None


# ------------------------------------------------------------------ recurrencias


def _parse_rule(value):
    rule = {}
    for part in value.split(";"):
        key, _, val = part.partition("=")
        if key:
            rule[key.upper()] = val
    return rule


def _check_rule(rule):
    freq = rule.get("FREQ", "").upper()
    if freq not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY") or not set(rule) <= SUPPORTED_RULE_KEYS:
        raise _Unsupported(freq)
    byday = [token for token in rule.get("BYDAY", "").upper().split(",") if token]
    if byday and (freq not in ("DAILY", "WEEKLY") or any(token not in WEEKDAYS for token in byday)):
        raise _Unsupported("BYDAY")
    if "BYMONTHDAY" in rule and freq != "MONTHLY":
        raise _Unsupported("BYMONTHDAY")
    try:
        if int(rule.get("INTERVAL", "1")) < 1:
            raise ValueError
        if "COUNT" in rule and int(rule["COUNT"]) < 1:
            raise ValueError
        if "BYMONTHDAY" in rule:
            [int(token) for token in rule["BYMONTHDAY"].split(",")]
    except ValueError as exc:
        raise _Unsupported("valores") from exc
    return freq, byday


def _until(value, start):
    value = value.strip()
    if re.fullmatch(r"\d{8}", value):
        return datetime.combine(datetime.strptime(value, "%Y%m%d").date(), time.max, tzinfo=start.tzinfo)
    if value.endswith(("Z", "z")):
        return datetime.strptime(value[:-1], "%Y%m%dT%H%M%S").replace(tzinfo=dt_timezone.utc)
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=start.tzinfo)


def _candidate_dates(start, freq, interval, byday, bymonthday):
    first = start.date()
    if freq == "DAILY":
        day = first
        while True:
            if not byday or day.weekday() in {WEEKDAYS[token] for token in byday}:
                yield day
            day += timedelta(days=interval)
    elif freq == "WEEKLY":
        anchor = first - timedelta(days=first.weekday())
        weekdays = sorted({WEEKDAYS[token] for token in byday}) or [first.weekday()]
        week = 0
        while True:
            base = anchor + timedelta(weeks=week * interval)
            for weekday in weekdays:
                day = base + timedelta(days=weekday)
                if day >= first:
                    yield day
            week += 1
    elif freq == "MONTHLY":
        year, month = first.year, first.month
        days = sorted(bymonthday) or [first.day]
        while True:
            for number in days:
                try:
                    day = date(year, month, number)
                except ValueError:
                    continue
                if day >= first:
                    yield day
            month += interval
            year, month = year + (month - 1) // 12, (month - 1) % 12 + 1
    else:  # YEARLY
        year = first.year
        while True:
            try:
                yield date(year, first.month, first.day)
            except ValueError:
                pass
            year += interval


def _occurrence_starts(start, rule_text, window_end, result):
    """Inicios de la serie hasta window_end, en la hora local del evento. Lanza _Unsupported si no se puede interpretar."""
    rule = _parse_rule(rule_text)
    freq, byday = _check_rule(rule)
    interval = int(rule.get("INTERVAL", "1"))
    count = int(rule["COUNT"]) if "COUNT" in rule else None
    bymonthday = [int(token) for token in rule.get("BYMONTHDAY", "").split(",") if token]
    try:
        until = _until(rule["UNTIL"], start) if "UNTIL" in rule else None
    except ValueError as exc:
        raise _Unsupported("UNTIL") from exc
    starts, produced = [], 0
    for step, day in enumerate(_candidate_dates(start, freq, interval, byday, bymonthday)):
        result.steps += 1
        if step > MAX_STEPS or result.steps > MAX_TOTAL_STEPS:
            raise _Unsupported("demasiadas repeticiones")
        occurrence = datetime.combine(day, start.time(), tzinfo=start.tzinfo)
        if until is not None and occurrence > until:
            break
        produced += 1
        if count is not None and produced > count:
            break
        if occurrence >= window_end:
            break
        starts.append(occurrence)
    return starts


# ------------------------------------------------------------------ interpretacion


def _event_span(event, default_tz, result):
    """(inicio, duracion) de un evento, o None si no ocupa tiempo (sin fin ni duracion)."""
    dtstart = _first(event, "DTSTART")
    if dtstart is None:
        raise _BadEvent("sin DTSTART")
    start, all_day = _parse_dt(dtstart[1], dtstart[0], default_tz, result)
    dtend, duration = _first(event, "DTEND"), _first(event, "DURATION")
    if dtend is not None:
        end, _ = _parse_dt(dtend[1], dtend[0], default_tz, result)
        length = end - start
    elif duration is not None:
        length = _parse_duration(duration[1])
    else:
        length = timedelta(days=1) if all_day else timedelta(0)
    return start, length


def _excluded(event, default_tz, result):
    values = set()
    for params, value in event.get("EXDATE", []):
        for item in value.split(","):
            if item.strip():
                parsed, all_day = _parse_dt(item, params, default_tz, result)
                values.add(parsed.date() if all_day else parsed)
    return values


def _is_free_or_cancelled(event):
    status, transp = _first(event, "STATUS"), _first(event, "TRANSP")
    return (status and status[1].strip().upper() == "CANCELLED") or (transp and transp[1].strip().upper() == "TRANSPARENT")


def parse_ics(text, default_tz, window_start, window_end) -> ImportResult:
    """Intervalos ocupados que tocan [window_start, window_end). Lanza ICSError si el archivo no es un calendario usable."""
    if "BEGIN:VCALENDAR" not in text.upper():
        raise ICSError("El archivo no parece un calendario (.ics). Exporta el calendario desde Google Calendar, Outlook o Apple Calendar.")
    events = _collect_events(_unfold(text))
    if not events:
        raise ICSError("El archivo no tiene eventos que importar.")
    if len(events) > MAX_EVENTS:
        raise ICSError(f"El archivo tiene más de {MAX_EVENTS} eventos. Exporta solo los próximos meses.")

    result = ImportResult(events=len(events))
    replaced = set()  # (uid, inicio original) de las instancias modificadas de una serie
    for event in events:
        recurrence_id, uid = _first(event, "RECURRENCE-ID"), _first(event, "UID")
        if recurrence_id and uid:
            try:
                original, _ = _parse_dt(recurrence_id[1], recurrence_id[0], default_tz, result)
                replaced.add((uid[1].strip(), original))
            except _BadEvent:
                pass

    for event in events:
        try:
            if _is_free_or_cancelled(event):
                continue
            span = _event_span(event, default_tz, result)
            start, length = span
            if length <= timedelta(0):
                continue
            starts = [start]
            rule = _first(event, "RRULE")
            if rule:
                excluded = _excluded(event, default_tz, result)
                uid = _first(event, "UID")
                try:
                    starts = _occurrence_starts(start, rule[1], window_end, result)
                except _Unsupported:
                    result.unsupported += 1
                    starts = [start]
                starts = [
                    s for s in starts
                    if s not in excluded and s.date() not in excluded
                    and not (uid and (uid[1].strip(), s) in replaced)
                ]
            for occurrence in starts:
                if occurrence < window_end and occurrence + length > window_start:
                    result.busy.append((occurrence, occurrence + length))
        except _BadEvent:
            result.skipped += 1
    if result.skipped == result.events:
        raise ICSError("No pudimos leer ningún evento del archivo. Verifica que sea un .ics exportado de tu calendario.")
    return result


def free_blocks(busy, week_start, tz, weekdays=range(5)) -> dict[str, int]:
    """Bloques de una hora, de lunes a viernes entre las 08:00 y las 22:00, que no se cruzan con ningun intervalo ocupado."""
    blocks = {}
    for day in weekdays:
        current = week_start + timedelta(days=day)
        for hour in HOURS:
            start = datetime.combine(current, time(hour), tzinfo=tz)
            end = start + timedelta(hours=1)
            if not any(b_start < end and b_end > start for b_start, b_end in busy):
                blocks[block_key(day, hour)] = AVAILABLE
    return blocks


def week_window(week_start, tz):
    start = datetime.combine(week_start, time.min, tzinfo=tz)
    return start, start + timedelta(days=7)
