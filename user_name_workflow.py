from __future__ import annotations
from dataclasses import dataclass
from livekit.agents import beta


@dataclass
class GetUserNameResult:
    name: str


class GetUserNameTask(beta.workflows.Workflow):
    def __init__(self, *, chat_ctx: beta.ChatContext) -> None:
        super().__init__(chat_ctx=chat_ctx)

    async def run(self) -> GetUserNameResult:
        prompt = "Quel est votre nom complet, s'il vous plaît ?"
        result = await beta.workflows.simple_text_input(
            chat_ctx=self._chat_ctx,
            prompt=prompt,
            max_retries=2,
            instructions="L'utilisateur va donner son nom. Renvoyez simplement le nom qu'il a fourni.",
        )
        return GetUserNameResult(name=result.text)
