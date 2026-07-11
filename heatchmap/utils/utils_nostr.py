# heatchmap - estimation and visualization of hitchhiking quality.
# Copyright (C) 2024 Till Wenke
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Fetch hitchhiking-ride events from Nostr relays.

Replaces the former ``hitchmap.com/dump.sqlite`` download. Ride records are
published to Nostr as kind-36820 events following the hitchhiking-data-standard
(https://github.com/Hitchwiki/hitchhiking-data-standard). Each event carries a
JSON ``content`` payload with the ride's stops, waiting duration and origin
``source`` (hitchmap.com, hitchwiki.org, liftershalte.info, maps.hitchwiki.org).

The fetched events are written to a small SQLite database with a ``points``
table (columns ``datetime``, ``lat``, ``lon``, ``wait``) so the rest of the
package can keep consuming them through :func:`heatchmap.utils.utils_data.get_points`.
"""

import asyncio
import json
import logging
import os
import re
import sqlite3

import pandas as pd
import websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Public relay serving the hitchhiking ride events.
DEFAULT_RELAYS = ["wss://relay.maps.hitchwiki.org"]
# Nostr event kind for hitchhiking rides (parameterized replaceable, addressable range).
RIDE_EVENT_KIND = 36820
# Hex public keys of the trusted submitters. Applied server-side as the Nostr
# "authors" filter so only rides signed by these keys are ever returned.
# See https://github.com/Hitchwiki/hitchhiking-data-standard/blob/main/nostr/README.md
TRUSTED_PUBKEYS = [
    "d17ff51bfc32d49217e8cb5bfa558a5a78e6cbe3ea4d947acbc7f11ca5c5dbd5",
    "6623bb9cbae2220e94d5f7581e0fd926db5d67538a08a7f306768e978d4d142e",
]
# The ride relay streams the full history in a single REQ (it does not clamp to
# the NIP-11 max_limit), so we ask for effectively "everything" and read until
# EOSE. A very high limit avoids the Nostr until/limit paging trap where a single
# second holding more than the page limit of events cannot be advanced past.
FETCH_LIMIT = 1_000_000
# Seconds to wait for the next relay message before giving up on the stream.
RECV_TIMEOUT = 90.0

# ISO-8601 duration, e.g. "PT100M", "PT1H30M", "P1DT2H". The date-part "M" means
# months (ambiguous in minutes) so we ignore years/months and only convert
# weeks/days/hours/minutes/seconds, which is all the ride data uses.
_ISO_DURATION = re.compile(
    r"^P(?:\d+Y)?(?:\d+M)?(?:(\d+)W)?(?:(\d+)D)?"
    r"(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$"
)


def _duration_to_minutes(iso: str | None) -> float | None:
    """Convert an ISO-8601 duration string to minutes, or None if unparseable/empty."""
    if not iso or not isinstance(iso, str):
        return None
    match = _ISO_DURATION.match(iso.strip())
    if not match:
        return None
    weeks, days, hours, minutes, seconds = match.groups()
    total = (
        (int(weeks) if weeks else 0) * 7 * 24 * 60
        + (int(days) if days else 0) * 24 * 60
        + (int(hours) if hours else 0) * 60
        + (int(minutes) if minutes else 0)
        + (float(seconds) if seconds else 0) / 60
    )
    return total if total > 0 else None


def parse_since(raw: str | None) -> int | None:
    """Resolve the ``SINCE`` config to a Unix timestamp in seconds (or None for full history).

    Accepts an ISO 8601 date/datetime (e.g. ``2026-01-01``) or a raw Unix timestamp.
    """
    if not raw or not str(raw).strip():
        return None
    raw = str(raw).strip()
    if raw.isdigit():
        return int(raw)
    ts = pd.to_datetime(raw, utc=True)
    return int(ts.timestamp())


async def _fetch_relay(relay: str, kind: int, authors: list[str] | None, since: int | None) -> dict:
    """Fetch the full history of ``kind`` events from a single relay.

    Issues one REQ with a very high limit and reads until EOSE. Returns a dict
    keyed by event id (dedup is by id, so a relay echoing an event more than once
    is harmless).
    """
    flt: dict = {"kinds": [kind], "limit": FETCH_LIMIT}
    if authors:
        flt["authors"] = authors
    if since is not None:
        flt["since"] = since

    sub_id = "hm" + os.urandom(4).hex()
    collected: dict[str, dict] = {}
    async with websockets.connect(relay, max_size=None, open_timeout=20) as ws:
        await ws.send(json.dumps(["REQ", sub_id, flt]))
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning(f"Timed out waiting for events from {relay}; stopping with {len(collected)} so far.")
                break
            msg = json.loads(raw)
            tag = msg[0]
            if tag == "EVENT" and msg[1] == sub_id:
                collected[msg[2]["id"]] = msg[2]
            elif tag == "EOSE" and msg[1] == sub_id:
                break
            elif tag == "CLOSED" and msg[1] == sub_id:
                logger.warning(f"Relay {relay} closed subscription: {msg}")
                break
            elif tag == "NOTICE":
                logger.info(f"Relay {relay} NOTICE: {msg[1:]}")
    logger.info(f"Fetched {len(collected)} events from {relay}.")
    return collected


async def _fetch_all_relays(relays: list[str], kind: int, authors: list[str] | None, since: int | None) -> list[dict]:
    """Fetch from all relays and merge unique events by id."""
    merged: dict[str, dict] = {}
    for relay in relays:
        try:
            merged.update(await _fetch_relay(relay, kind, authors, since))
        except Exception as e:  # noqa: BLE001 - one bad relay should not abort the rest
            logger.warning(f"Failed to fetch from {relay}: {e}")
    return sorted(merged.values(), key=lambda ev: ev["created_at"])


def events_to_dataframe(events: list[dict], source: str | None = None) -> pd.DataFrame:
    """Turn raw Nostr ride events into a ``(datetime, lat, lon, wait)`` DataFrame.

    - ``datetime``: the event's ``created_at`` (when the record became available),
      used downstream to decide which points are new since the last map update.
    - ``lat``/``lon``: the first stop's location (the pickup point).
    - ``wait``: waiting time in minutes, from the first stop's ``waiting_duration``,
      falling back to the first signal's ``duration``. May be NaN when absent.

    ``source`` optionally keeps only rides from that origin app (client-side, since
    relays cannot filter on content). None keeps every source.
    """
    rows = []
    skipped = 0
    for ev in events:
        try:
            content = json.loads(ev.get("content") or "{}")
        except (json.JSONDecodeError, TypeError):
            skipped += 1
            continue

        if source is not None and content.get("source") != source:
            continue

        stops = content.get("stops") or []
        if not stops or not isinstance(stops[0], dict):
            skipped += 1
            continue
        location = stops[0].get("location") or {}
        lat = location.get("latitude")
        lon = location.get("longitude")
        if lat is None or lon is None:
            skipped += 1
            continue

        wait = _duration_to_minutes(stops[0].get("waiting_duration"))
        if wait is None:
            signals = content.get("signals") or []
            if signals and isinstance(signals[0], dict):
                wait = _duration_to_minutes(signals[0].get("duration"))

        rows.append(
            {
                "datetime": pd.to_datetime(ev.get("created_at"), unit="s"),
                "lat": lat,
                "lon": lon,
                "wait": wait,
            }
        )

    if skipped:
        logger.info(f"Skipped {skipped} events with unparseable content or missing location.")
    return pd.DataFrame(rows, columns=["datetime", "lat", "lon", "wait"])


def download_nostr_points(
    db_path: str,
    relays: list[str] | None = None,
    kind: int | None = None,
    pubkeys: list[str] | None = None,
    since: int | None = None,
    source: str | None = None,
) -> int:
    """Fetch ride events from Nostr and write them to ``db_path`` as a ``points`` table.

    Configuration falls back to environment variables matching the
    hitchhiking-data-standard fetcher (``RELAYS``, ``NOSTR_EVENT_KIND``,
    ``PUBKEYS``, ``SINCE``, ``SOURCE``) and then to the module defaults.

    Returns the number of ride points written. Raises if the fetch yields no
    events, so callers can fall back to a previously cached database.
    """
    if relays is None:
        relays = json.loads(os.environ["RELAYS"]) if os.environ.get("RELAYS") else DEFAULT_RELAYS
    if kind is None:
        kind = int(os.environ.get("NOSTR_EVENT_KIND", RIDE_EVENT_KIND))
    if pubkeys is None:
        pubkeys = json.loads(os.environ["PUBKEYS"]) if os.environ.get("PUBKEYS") else TRUSTED_PUBKEYS
    if since is None:
        since = parse_since(os.environ.get("SINCE"))
    if source is None:
        source = os.environ.get("SOURCE") or None

    logger.info(f"Fetching Nostr ride events (kind {kind}) from {relays}...")
    events = asyncio.run(_fetch_all_relays(relays, kind, pubkeys, since))
    logger.info(f"Fetched {len(events)} unique ride events from Nostr.")

    df = events_to_dataframe(events, source=source)
    if len(df) == 0:
        raise ValueError("Nostr fetch returned no usable ride points.")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        df.to_sql("points", connection, if_exists="replace", index=False)
    logger.info(f"Wrote {len(df)} ride points to {db_path}.")
    return len(df)
