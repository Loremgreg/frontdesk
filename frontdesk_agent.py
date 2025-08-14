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
                f"Tu es Front-Desk, un assistant vocal utile, efficace et courtois. "
                f"Nous sommes le {today}. Ta mission principale est d’aider l’utilisateur à réserver un rendez-vous. "
                "La conversation est vocale — parle naturellement, clairement et avec concision. "
                "Commence toujours par saluer chaleureusement l’utilisateur, puis oriente immédiatement vers la prise de rendez‑vous ou demande s’il a une question. "
                "Lorsque l’utilisateur te salue, ne te contente pas d’un simple bonjour : saisis l’occasion pour faire avancer la démarche. "
                "Par exemple, enchaîne avec : ‘Souhaitez-vous réserver un horaire ?’. "
                "IMPORTANT : Quand tu dois consulter une information qui peut prendre du temps (comme vérifier le calendrier avec `list_available_slots`), annonce-le d’abord. Par exemple : ‘Un instant, je consulte les disponibilités pour vous.’ puis appelle la fonction. "
                "Une fois que tu as la liste des créneaux, NE LA LIS PAS EN ENTIER. Synthétise-la en proposant des options générales. Par exemple : 'J'ai plusieurs créneaux disponibles en début de semaine prochaine, notamment lundi matin et mardi après-midi.' ou 'Je vois des disponibilités pour jeudi en fin de journée.' Ensuite, demande à l\'utilisateur ce qui l\'arrangerait pour affiner la recherche. "
                "Formule des créneaux comme ‘lundi en fin de matinée’ ou ‘mardi en début d’après-midi’ — évite les fuseaux horaires, les timestamps, et évite de dire ‘AM’ ou ‘PM’. "
                "Ne mentionne l’année que si elle est différente de l’année en cours. "
                "Propose quelques options à la fois, marque une pause pour la réponse, puis guide l’utilisateur vers la confirmation. "
                "Si le créneau n’est plus disponible, informe‑le avec tact et propose les options suivantes. "
                "Lorsque tu demandes des informations (email, numéro de téléphone, nom et prénom), pose la question directement, sans répéter la phrase 'Pour finaliser la réservation'. "
                "Exemples : 'Pourriez‑vous me fournir votre adresse email ?', 'Pourriez‑vous également me fournir votre numéro de téléphone ?', 'Pourriez‑vous me donner votre nom et prénom, s'il vous plaît ?'. "
                "IMPORTANT pour les emails : Si tu ne comprends pas bien une adresse email, demande poliment à l'utilisateur de l'épeler lettre par lettre. "
                "Si une information n'est pas claire, dis explicitement : 'Je n'ai pas bien compris, pouvez-vous répéter plus lentement ?' "
                "Garde toujours la conversation fluide — sois proactif, naturel et centré sur l'objectif : aider l'utilisateur à réserver facilement."
            )
        )

        self._slots_map: dict[str, AvailableSlot] = {}

    async def start(self, ctx: AgentSession) -> None:
        """
        Commence toujours par saluer chaleureusement l’utilisateur, 
        puis oriente immédiatement vers la prise de rendez‑vous ou demande s’il a une question
        """
        await super().start(ctx)
        await self.chat_ctx.say(
            "Bonjour et bienvenue ! Je suis l'assistant du salon. "
            "Souhaitez-vous prendre un rendez-vous ou avez-vous une question ?",
            add_to_chat_ctx=False,  # Don't add the initial greeting to the LLM context
        )

    @function_tool
    async def schedule_appointment(
        self,
        ctx: RunContext[Userdata],
        slot_id: str,
        user_name: str,
        user_email: str,
        user_phone_number: str,
    ) -> str | None:
        """
        Schedule an appointment at the given slot using the user's information.

        Args:
            slot_id: The identifier for the selected time slot.
            user_name: The full name of the user.
            user_email: The email address of the user.
            user_phone_number: The phone number of the user.
        """
        if not (slot := self._slots_map.get(slot_id)):
            raise ToolError(f"error: slot {slot_id} was not found")

        ctx.disallow_interruptions()
        
        try:
            # The user information is now passed directly as arguments.
            # No need to call the workflows here anymore.
            
            await ctx.userdata.cal.schedule_appointment(
                start_time=slot.start_time,
                attendee_email=user_email,
                user_name=user_name,
            )
            
            local = slot.start_time.astimezone(self.tz)
            appointment_details = f"{local.strftime('%A, %B %d, %Y at %H:%M %Z')}"
            
            # Use the provided phone number to send the SMS
            sms_sent = sms_manager.send_confirmation_sms(
                user_phone_number, appointment_details, language="de"
            )

            confirmation_message = (
                f"Vielen Dank, {user_name}. Der Termin wurde erfolgreich für {appointment_details} vereinbart."
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
            
        except SlotUnavailableError:
            raise ToolError("This slot isn't available anymore") from None
        except Exception as e:
            logger.error(f"Erreur lors de la réservation: {e}")
            raise ToolError(f"Je rencontre un problème technique lors de la réservation. Pouvez-vous réessayer ?") from None

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

    # SÉCURITÉ: Éviter d'exposer les credentials dans os.environ
    # Créer l'auth header directement sans le stocker dans les variables d'environnement système
    langfuse_auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    endpoint = f"{host.rstrip('/')}/api/public/otel"
    headers = {"Authorization": f"Basic {langfuse_auth}"}

    # Configurer l'exporter directement avec les headers sécurisés
    trace_provider = TracerProvider()
    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers=headers
    )
    trace_provider.add_span_processor(BatchSpanProcessor(exporter))
    set_tracer_provider(trace_provider)


async def entrypoint(ctx: JobContext):
    setup_langfuse()
    await ctx.connect()

    timezone = "utc"
    
    # Debug: Vérifier les variables d'environnement
    cal_api_key = os.getenv("CAL_API_KEY", None)
    logger.info("🔍 Checking calendar configuration...")
    logger.info(f"🔑 CAL_API_KEY present: {bool(cal_api_key)}")
    if cal_api_key:
        logger.info(f"🔑 CAL_API_KEY prefix: {cal_api_key[:10]}...")
    
    if cal_api_key:
        logger.info("✅ CAL_API_KEY detected, using Cal.com calendar")
        cal = CalComCalendar(api_key=cal_api_key, timezone=timezone)
        logger.info("📅 CalComCalendar instance created")
    else:
        logger.warning(
            "⚠️  CAL_API_KEY is not set. Falling back to FakeCalendar; set CAL_API_KEY to enable Cal.com integration."
        )
        cal = FakeCalendar(timezone=timezone)
        logger.info("🎭 FakeCalendar instance created")

    logger.info("🔧 Initializing calendar...")
    try:
        await cal.initialize()
        logger.info("✅ Calendar initialization completed successfully")
    except Exception as e:
        logger.error(f"💥 Calendar initialization failed: {type(e).__name__}: {e}")
        logger.error("🎭 Falling back to FakeCalendar due to initialization error")
        cal = FakeCalendar(timezone=timezone)
        await cal.initialize()
        logger.info("✅ FakeCalendar fallback initialized")

    session = AgentSession[Userdata](
        userdata=Userdata(cal=cal),
        preemptive_generation=True,
        stt=deepgram.STT(
            language="fr",
            endpointing_ms=1200,  # Augmenté de 500 à 1200ms pour les emails
            punctuate=True,
            smart_format=True
        ),
        llm=openai.LLM(model="gpt-4o-mini", parallel_tool_calls=False, temperature=0.45),
                tts=elevenlabs.TTS(model="eleven_flash_v2_5"),
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),
        max_tool_steps=1,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("new_chat_message")
    def on_new_chat_message(msg):
        # Simple logger to see the conversation flow in the terminal
        print(f"[{msg.role.upper()}]: {msg.content}")

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
