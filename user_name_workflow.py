from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
from livekit.agents import AgentTask, RunContext, function_tool, beta, ToolError
from livekit.agents.types import NotGiven, NOT_GIVEN

if TYPE_CHECKING:
    from livekit.agents.session import TurnDetectionMode
    from livekit.agents import llm, stt, tts, vad


@dataclass
class GetUserNameResult:
    name: str


class GetUserNameTask(AgentTask[GetUserNameResult]):
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
                "Vous êtes responsable uniquement de recueillir le nom de l'utilisateur.\n"
                "Demandez poliment le nom complet de l'utilisateur et enregistrez-le.\n"
                "Appelez `update_name` dès que vous avez une hypothèse sur le nom de l'utilisateur.\n"
                "Appelez `confirm_name` après que l'utilisateur a confirmé que le nom est correct."
            ),
            chat_ctx=chat_ctx,
            turn_detection=turn_detection,
            stt=stt,
            vad=vad,
            llm=llm,
            tts=tts,
            allow_interruptions=allow_interruptions,
        )
        self._current_name = ""

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions="Demandez poliment à l'utilisateur son nom complet."
        )

    @function_tool
    async def update_name(self, name: str, ctx: RunContext) -> str:
        """Mettre à jour le nom fourni par l'utilisateur.
        
        Args:
            name: Le nom fourni par l'utilisateur
        """
        self._current_name = name.strip()
        
        return (
            f"Le nom a été mis à jour à {self._current_name}\n"
            f"Demandez à l'utilisateur de confirmer que c'est correct."
        )

    @function_tool
    async def confirm_name(self, ctx: RunContext) -> None:
        """Confirme le nom fourni par l'utilisateur."""
        await ctx.wait_for_playout()
        
        if not self._current_name.strip():
            raise ToolError(
                "erreur: aucun nom n'a été fourni, `update_name` doit être appelé avant"
            )
            
        if not self.done():
            self.complete(GetUserNameResult(name=self._current_name))
