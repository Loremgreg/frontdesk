from __future__ import annotations

import base64
import datetime
import hashlib
import logging
import random
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import aiohttp

from livekit.agents.utils import http_context


class SlotUnavailableError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass
class AvailableSlot:
    start_time: datetime.datetime
    duration_min: int

    @property
    def unique_hash(self) -> str:
        # unique id based on the start_time & duration_min
        raw = f"{self.start_time.isoformat()}|{self.duration_min}".encode()
        digest = hashlib.blake2s(raw, digest_size=5).digest()
        return f"ST_{base64.b32encode(digest).decode().rstrip('=').lower()}"


class Calendar(Protocol):
    async def initialize(self) -> None: ...
    async def schedule_appointment(
        self,
        *,
        start_time: datetime.datetime,
        attendee_email: str,
        user_name: str,
    ) -> None: ...
    async def list_available_slots(
        self, *, start_time: datetime.datetime, end_time: datetime.datetime
    ) -> list[AvailableSlot]: ...


class FakeCalendar(Calendar):
    def __init__(self, *, timezone: str, slots: list[AvailableSlot] | None = None) -> None:
        self.tz = ZoneInfo(timezone)
        self._slots: list[AvailableSlot] = []

        if slots is not None:
            self._slots.extend(slots)
            return

        today = datetime.datetime.now(self.tz).date()
        for day_offset in range(1, 90):  # generate slots for the next 90 days
            current_day = today + datetime.timedelta(days=day_offset)
            if current_day.weekday() >= 5:
                continue

            # build all possible 30-min slots between 09:00 and 17:00
            day_start = datetime.datetime.combine(current_day, datetime.time(9, 0), tzinfo=self.tz)
            slots_in_day = [
                day_start + datetime.timedelta(minutes=30 * i)
                for i in range(int((17 - 9) * 2))  # (17-9)=8 hours => 16 slots
            ]

            num_slots = random.randint(3, 6)
            chosen = random.sample(slots_in_day, num_slots)

            for slot_start in sorted(chosen):
                self._slots.append(AvailableSlot(start_time=slot_start, duration_min=30))

    async def initialize(self) -> None:
        pass

    async def schedule_appointment(
        self, *, start_time: datetime.datetime, attendee_email: str, user_name: str
    ) -> None:
        # fake it by just removing it from our slots list
        self._slots = [slot for slot in self._slots if slot.start_time != start_time]

    async def list_available_slots(
        self, *, start_time: datetime.datetime, end_time: datetime.datetime
    ) -> list[AvailableSlot]:
        return [slot for slot in self._slots if start_time <= slot.start_time < end_time]


# --- cal.com impl ---

CAL_COM_EVENT_TYPE = "livekit-front-desk"
EVENT_DURATION_MIN = 30
BASE_URL = "https://api.cal.com/v2/"


class CalComCalendar(Calendar):
    def __init__(self, *, api_key: str, timezone: str) -> None:
        self.tz = ZoneInfo(timezone)
        self._api_key = api_key

        try:
            self._http_session = http_context.http_session()
        except RuntimeError:
            self._http_session = aiohttp.ClientSession()

        self._logger = logging.getLogger("cal.com")

    async def initialize(self) -> None:
        self._logger.info("🔧 Initializing Cal.com calendar integration...")
        self._logger.info(f"🌐 Base URL: {BASE_URL}")
        self._logger.info(f"🔑 API Key present: {bool(self._api_key)}")
        self._logger.info(f"🔑 API Key prefix: {self._api_key[:10] if self._api_key else 'None'}...")
        
        try:
            # Test API connection and get user info
            self._logger.info("👤 Fetching user information...")
            async with self._http_session.get(
                headers=self._build_headers(api_version="2024-06-14"), url=f"{BASE_URL}me/"
            ) as resp:
                self._logger.info(f"📡 /me/ response status: {resp.status}")
                resp.raise_for_status()
                user_data = await resp.json()
                self._logger.info(f"👤 User data received: {user_data}")
                username = user_data["data"]["username"]
                self._logger.info(f"✅ Using cal.com username: {username}")

            # Get or create event type
            self._logger.info(f"📅 Looking for event type: {CAL_COM_EVENT_TYPE}")
            query = urlencode({"username": username})
            async with self._http_session.get(
                headers=self._build_headers(api_version="2024-06-14"),
                url=f"{BASE_URL}event-types/?{query}",
            ) as resp:
                self._logger.info(f"📡 /event-types/ response status: {resp.status}")
                resp.raise_for_status()
                event_types_data = await resp.json()
                self._logger.info(f"📅 Event types data: {event_types_data}")
                data = event_types_data["data"]
                lk_event_type = next(
                    (event for event in data if event.get("slug") == CAL_COM_EVENT_TYPE), None
                )

                if lk_event_type:
                    self._lk_event_id = lk_event_type["id"]
                    self._logger.info(f"✅ Found existing event type: {lk_event_type}")
                else:
                    self._logger.info(f"🆕 Creating new event type: {CAL_COM_EVENT_TYPE}")
                    create_payload = {
                        "lengthInMinutes": EVENT_DURATION_MIN,
                        "title": "LiveKit Front-Desk",
                        "slug": CAL_COM_EVENT_TYPE,
                    }
                    self._logger.info(f"📋 Create event type payload: {create_payload}")
                    
                    async with self._http_session.post(
                        headers=self._build_headers(api_version="2024-06-14"),
                        url=f"{BASE_URL}event-types",
                        json=create_payload,
                    ) as resp:
                        self._logger.info(f"📡 Create event type response status: {resp.status}")
                        resp.raise_for_status()
                        create_response = await resp.json()
                        self._logger.info(f"🆕 Event type created: {create_response}")
                        self._logger.info(f"✅ Successfully added {CAL_COM_EVENT_TYPE} event type")
                        data = create_response["data"]
                        self._lk_event_id = data["id"]

                self._logger.info(f"🎯 Final event type ID: {self._lk_event_id}")
                self._logger.info("✅ Cal.com calendar initialization completed successfully!")
                
        except Exception as e:
            self._logger.error(f"💥 Cal.com initialization failed: {type(e).__name__}: {e}")
            raise

    async def schedule_appointment(
        self, *, start_time: datetime.datetime, attendee_email: str, user_name: str
    ) -> None:
        start_time = start_time.astimezone(datetime.timezone.utc)
        
        payload = {
            "start": start_time.isoformat(),
            "attendee": {
                "name": user_name,
                "email": attendee_email,
                "timeZone": self.tz.key,
            },
            "eventTypeId": self._lk_event_id,
        }
        
        self._logger.info(f"🚀 Attempting to create booking with payload: {payload}")
        self._logger.info(f"📅 Booking URL: {BASE_URL}bookings")
        self._logger.info(f"🔑 Using event type ID: {self._lk_event_id}")

        try:
            async with self._http_session.post(
                headers=self._build_headers(api_version="2024-08-13"),
                url=f"{BASE_URL}bookings",
                json=payload,
            ) as resp:
                self._logger.info(f"📡 HTTP Response Status: {resp.status}")
                
                # Lire la réponse
                response_text = await resp.text()
                self._logger.info(f"📄 Raw response: {response_text}")
                
                try:
                    data = await resp.json() if response_text else {}
                except Exception as json_error:
                    self._logger.error(f"❌ Failed to parse JSON response: {json_error}")
                    self._logger.error(f"Raw response was: {response_text}")
                    raise
                
                self._logger.info(f"📋 Parsed Cal.com response: {data}")
                
                if error := data.get("error"):
                    message = error["message"]
                    self._logger.error(f"❌ Cal.com API error: {message}")
                    self._logger.error(f"Full error details: {error}")
                    if "User either already has booking at this time or is not available" in message:
                        raise SlotUnavailableError(error["message"])
                    # Raise other errors too
                    raise Exception(f"Cal.com API error: {message}")

                # Check HTTP status
                if resp.status >= 400:
                    self._logger.error(f"❌ HTTP Error {resp.status}: {response_text}")
                    resp.raise_for_status()
                
                self._logger.info("✅ Booking created successfully in Cal.com!")
                self._logger.info(f"📋 Booking details: {data}")
                
        except Exception as e:
            self._logger.error(f"💥 Exception during booking creation: {type(e).__name__}: {e}")
            raise

    async def list_available_slots(
        self, *, start_time: datetime.datetime, end_time: datetime.datetime
    ) -> list[AvailableSlot]:
        try:
            start_time = start_time.astimezone(datetime.timezone.utc)
            end_time = end_time.astimezone(datetime.timezone.utc)
            query = urlencode(
                {
                    "eventTypeId": self._lk_event_id,
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                }
            )
            async with self._http_session.get(
                headers=self._build_headers(api_version="2024-09-04"), url=f"{BASE_URL}slots/?{query}"
            ) as resp:
                resp.raise_for_status()
                response_json = await resp.json()
                
                if "data" not in response_json:
                    self._logger.error(f"Unexpected API response format: {response_json}")
                    return []
                    
                raw_data = response_json["data"]
                
                available_slots = []
                for _, slots in raw_data.items():
                    if not isinstance(slots, list):
                        continue
                        
                    for slot in slots:
                        if not isinstance(slot, dict) or "start" not in slot:
                            continue
                            
                        try:
                            start_dt = datetime.datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
                            available_slots.append(
                                AvailableSlot(start_time=start_dt, duration_min=EVENT_DURATION_MIN)
                            )
                        except (ValueError, AttributeError) as e:
                            self._logger.error(f"Error parsing slot start time: {e}")
                            continue
                            
                return available_slots
        except Exception as e:
            self._logger.error(f"Error fetching available slots: {e}")
            return []

    def _build_headers(self, *, api_version: str | None = None) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self._api_key}"}
        if api_version:
            h["cal-api-version"] = api_version
        return h