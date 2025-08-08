from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from livekit.agents import (
    llm,
    stt,
    tts,
    vad,
    AgentTask,
    RunContext,
    ToolError,
    function_tool,
)
from livekit.agents.types import NotGiven, NOT_GIVEN
from livekit.agents.voice import SpeechHandle

if TYPE_CHECKING:
    from livekit.agents.session import TurnDetectionMode

# Regular expression for international phone numbers
PHONE_REGEX = r'^\+?[1-9]\d{1,14}$'

@dataclass
class GetPhoneNumberResult:
    phone_number: str

class GetPhoneNumberTask(AgentTask[GetPhoneNumberResult]):
    def __init__(
        self,
        chat_ctx: NotGiven[llm.ChatContext] = NOT_GIVEN,
        turn_detection: NotGiven[TurnDetectionMode | None] = NOT_GIVEN,
        stt: NotGiven[stt.STT | None] = NOT_GIVEN,
        vad: NotGiven[vad.VAD | None] = NOT_GIVEN,
        llm: NotGiven[llm.LLM | llm.RealtimeModel | None] = NOT_GIVEN,
        tts: NotGiven[tts.TTS | None] = NOT_GIVEN,
        allow_interruptions: NotGiven[bool] = NOT_GIVEN,
    ) -> None:
        super().__init__(
            instructions=(
                "You are only a single step in a broader system, responsible solely for capturing a phone number.\n"
                "Handle input as noisy voice transcription. Expect that users will say phone numbers aloud with formats like:\n"
                "- 'null sechs drei sechs drei sechs drei sechs drei sechs' (for 0636363636)\n"
                "- 'plus drei drei sechs drei sechs drei sechs drei sechs drei sechs' (for +33636363636)\n"
                "- 'sechs drei sechs drei sechs drei sechs drei sechs' (for 636363636)\n"
                "- 'null sechs' followed by individual digits\n"
                "Normalize common spoken patterns silently:\n"
                "- Convert words like 'null', 'eins', 'zwei', etc. into digits: '0', '1', '2', etc.\n"
                "- Recognize 'plus' as '+' for international prefix.\n"
                "- Handle common German phone number formats (10 digits starting with 0, or international format with +49).\n"
                "Don't mention corrections. Treat inputs as possibly imperfect but fix them silently.\n"
                "Call `update_phone_number` at the first opportunity whenever you form a new hypothesis about the phone number. "
                "(before asking any questions or providing any answers.) \n"
                "Don't invent new phone numbers, stick strictly to what the user said. \n"
                "Call `confirm_phone_number` after the user confirmed the phone number is correct. \n"
                "If the phone number is unclear or invalid, or it takes too much back-and-forth, prompt for it in parts: first the prefix, then the digits—only if needed. \n"
                "Ignore unrelated input and avoid going off-topic. Do not generate markdown, greetings, or unnecessary commentary. \n"
                "Always explicitly invoke a tool when applicable. Do not simulate tool usage, no real action is taken unless the tool is explicitly called."
            ),
            chat_ctx=chat_ctx,
            turn_detection=turn_detection,
            stt=stt,
            vad=vad,
            llm=llm,
            tts=tts,
            allow_interruptions=allow_interruptions,
        )

        self._current_phone_number = ""
        # speech_handle/turn used to update the phone number.
        # used to ignore the call to confirm_phone_number in case the LLM is hallucinating and not asking for user confirmation
        self._phone_update_speech_handle: SpeechHandle | None = None

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions=(
                "Ask the user to provide a phone number. If you already have it, ask for confirmation.\n"
                "Do not call `decline_phone_number_capture`"
            )
        )

    @function_tool
    async def update_phone_number(self, phone: str, ctx: RunContext) -> str:
        """Update the phone number provided by the user.
        
        Args:
            phone: The phone number provided by the user
        """
        self._phone_update_speech_handle = ctx.speech_handle
        phone = phone.strip()
        
        # Remove all non-digit characters except + at the beginning
        digits = re.sub(r'[^\d+]', '', phone)
        
        # Handle French mobile numbers that start with 0
        if digits.startswith('0') and len(digits) == 10:
            digits = '+33' + digits[1:]
        
        # Validate the phone number format
        if not re.match(PHONE_REGEX, digits):
            raise ToolError(f"Invalid phone number format: {phone}")
            
        self._current_phone_number = digits
        separated_phone = " ".join(digits)
        
        return (
            f"The phone number has been updated to {digits}\n"
            f"Repeat the phone number character by character: {separated_phone} if needed\n"
            f"Prompt the user for confirmation, do not call `confirm_phone_number` directly"
        )

    @function_tool
    async def confirm_phone_number(self, ctx: RunContext) -> None:
        """Validates/confirms the phone number provided by the user."""
        await ctx.wait_for_playout() 
        
        if ctx.speech_handle == self._phone_update_speech_handle:
            raise ToolError("error: the user must confirm the phone number explicitly")
            
        if not self._current_phone_number.strip():
            raise ToolError(
                "error: no phone number was provided, `update_phone_number` must be called before"
            )
            
        if not self.done():
            self.complete(GetPhoneNumberResult(phone_number=self._current_phone_number))

    @function_tool
    async def decline_phone_number_capture(self, reason: str) -> None:
        """Handles the case when the user explicitly declines to provide a phone number.
        
        Args:
            reason: A short explanation of why the user declined to provide the phone number
        """
        if not self.done():
            self.complete(ToolError(f"couldn't get the phone number: {reason}"))