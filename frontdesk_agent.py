from __future__ import annotations

import asyncio
import datetime
import logging
import os
import sys
from dataclasses import dataclass
from typing import Literal
from zoneinfo import ZoneInfo

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from calendar_api import AvailableSlot, CalComCalendar, Calendar, FakeCalendar, SlotUnavailableError
from dotenv import load_dotenv
from phone_number_workflow import GetPhoneNumberTask, GetPhoneNumberResult
from user_name_workflow import GetUserNameTask, GetUserNameResult
from sms_manager import SMSManager

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    MetricsCollectedEvent,
    RunContext,
    ToolError,
    WorkerOptions,
    beta,
    cli,
    function_tool,
    metrics,
)
from livekit.plugins import elevenlabs, deepgram, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv()


@dataclass
class Userdata:
    cal: Calendar


logger = logging.getLogger("front-desk")

# Initialize SMS manager
sms_manager = SMSManager()

class FrontDeskAgent(Agent):
    def __init__(self, *, timezone: str) -> None:
        self.tz = ZoneInfo(timezone)
        today = datetime.datetime.now(self.tz).strftime("%A, %B %d, %Y")

        super().__init__(
            instructions=(
                f"You are Front-Desk, a helpful and efficient voice assistant. "
                f"Today is {today}. Your main goal is to schedule an appointment for the user. "
                "This is a voice conversation — speak naturally, clearly, and concisely. "
                "When the user says hello or greets you, don’t just respond with a greeting — use it as an opportunity to move things forward. "
                "For example, follow up with a helpful question like: 'Would you like to book a time?' "
                "When asked for availability, call list_available_slots and offer a few clear, simple options. "
                "Say things like 'Monday at 2 PM' — avoid timezones, timestamps, and avoid saying 'AM' or 'PM'. "
                "Use natural phrases like 'in the morning' or 'in the evening', and don’t mention the year unless it’s different from the current one. "
                "Offer a few options at a time, pause for a response, then guide the user to confirm. "
                "If the time is no longer available, let them know gently and offer the next options. "
                "Always keep the conversation flowing — be proactive, human, and focused on helping the user schedule with ease."
            )
        )

        self._slots_map: dict[str, AvailableSlot] = {}

    @function_tool
    async def schedule_appointment(
        self,
        ctx: RunContext[Userdata],
        slot_id: str,
    ) -> str | None:
        """
        Schedule an appointment at the given slot.

        Args:
            slot_id: The identifier for the selected time slot (as shown in the list of available slots).
        """
        if not (slot := self._slots_map.get(slot_id)):
            raise ToolError(f"error: slot {slot_id} was not found")

        # Get email address from user
        email_result = await beta.workflows.GetEmailTask(chat_ctx=self.chat_ctx)

        if ctx.speech_handle.interrupted:
            return

        # Get phone number from user
        phone_result = await GetPhoneNumberTask(chat_ctx=self.chat_ctx)

        if ctx.speech_handle.interrupted:
            return

        # Get user name from user
        name_result = await GetUserNameTask(chat_ctx=self.chat_ctx)

        if ctx.speech_handle.interrupted:
            return

        ctx.disallow_interruptions()

        try:
            await ctx.userdata.cal.schedule_appointment(
                start_time=slot.start_time,
                attendee_email=email_result.email_address,
                user_name=name_result.name,
            )
        except SlotUnavailableError:
            # exceptions other than ToolError are treated as "An internal error occured" for the LLM.
            # Tell the LLM this slot isn't available anymore
            raise ToolError("This slot isn't available anymore") from None

        # Send SMS confirmation in German
        local = slot.start_time.astimezone(self.tz)
        appointment_details = f"{local.strftime('%A, %B %d, %Y at %H:%M %Z')}"
        sms_sent = sms_manager.send_confirmation_sms(
            phone_result.phone_number, appointment_details, language="de"
        )

        confirmation_message = (
            f"Vielen Dank, {name_result.name}. Der Termin wurde erfolgreich für {appointment_details} vereinbart."
        )
        if sms_sent:
            confirmation_message += (
                " Eine Bestätigungs-SMS wurde an Ihre Telefonnummer gesendet."
            )
        else:
            confirmation_message += (
                " Wir konnten keine Bestätigungs-SMS an Ihre Telefonnummer senden."
            )
            
        return confirmation_message

    @function_tool
    async def list_available_slots(
        self, ctx: RunContext[Userdata], range: Literal["+2week", "+1month", "+3month", "default"]
    ) -> str:
        """
        Return a plain-text list of available slots, one per line.

        <slot_id> – <Weekday>, <Month> <Day>, <Year> at <HH:MM> <TZ> (<relative time>)

        You must infer the appropriate ``range`` implicitly from the
        conversational context and **must not** prompt the user to pick a value
        explicitly.

        Args:
            range: Determines how far ahead to search for free time slots.
        """
        # Let the user know we're working on it. This plays audio while we wait for the calendar API.
        # The task runs in the background and we don't await it.
        async def say_waiting_message():
            try:
                await self.chat_ctx.say(
                    "Un instant, je consulte les disponibilités pour vous.",
                    add_to_chat_ctx=False,
                )
            except Exception as e:
                logger.error(f"Error in background task: {e}")
                
        asyncio.create_task(say_waiting_message())

        now = datetime.datetime.now(self.tz)
        lines: list[str] = []

        if range == "+2week" or range == "default":
            range_days = 14
        elif range == "+1month":
            range_days = 30
        elif range == "+3month":
            range_days = 90

        for slot in await ctx.userdata.cal.list_available_slots(
            start_time=now, end_time=now + datetime.timedelta(days=range_days)
        ):
            local = slot.start_time.astimezone(self.tz)
            delta = local - now
            days = delta.days
            seconds = delta.seconds

            if local.date() == now.date():
                if seconds < 3600:
                    rel = "in less than an hour"
                else:
                    rel = "later today"
            elif local.date() == (now.date() + datetime.timedelta(days=1)):
                rel = "tomorrow"
            elif days < 7:
                rel = f"in {days} days"
            elif days < 14:
                rel = "in 1 week"
            else:
                rel = f"in {days // 7} weeks"

            lines.append(
                f"{slot.unique_hash} – {local.strftime('%A, %B %d, %Y')} at "
                f"{local:%H:%M} {local.tzname()} ({rel})"
            )
            self._slots_map[slot.unique_hash] = slot

        return "\n".join(lines) or "No slots available at the moment."


import base64
from livekit.agents.telemetry import set_tracer_provider


def setup_langfuse(
    host: str | None = None, public_key: str | None = None, secret_key: str | None = None
):
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
    host = host or os.getenv("LANGFUSE_HOST")

    if not public_key or not secret_key or not host:
        logger.warning(
            "Langfuse telemetry is not configured. Set LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_HOST to enable."
        )
        return

    langfuse_auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{host.rstrip('/')}/api/public/otel"
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {langfuse_auth}"

    trace_provider = TracerProvider()
    trace_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    set_tracer_provider(trace_provider)


async def entrypoint(ctx: JobContext):
    setup_langfuse()
    await ctx.connect()

    timezone = "utc"

    if cal_api_key := os.getenv("CAL_API_KEY", None):
        logger.info("CAL_API_KEY detected, using cal.com calendar")
        cal = CalComCalendar(api_key=cal_api_key, timezone=timezone)
    else:
        logger.warning(
            "CAL_API_KEY is not set. Falling back to FakeCalendar; set CAL_API_KEY to enable Cal.com integration."
        )
        cal = FakeCalendar(timezone=timezone)

    await cal.initialize()

    session = AgentSession[Userdata](
        userdata=Userdata(cal=cal),
        preemptive_generation=True,
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o", parallel_tool_calls=False, temperature=0.45),
                tts=elevenlabs.TTS(model="eleven_flash_v2_5"),
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),
        max_tool_steps=1,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)
        metrics.log_metrics(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)


    await session.start(agent=FrontDeskAgent(timezone=timezone), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="frontdesk_agent"))