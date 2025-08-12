
import os
import pytest
from dotenv import load_dotenv

from livekit.agents import AgentSession, llm
from livekit.plugins import openai

# On importe le vrai calendrier et non le FakeCalendar
from calendar_api import CalComCalendar
from frontdesk_agent import FrontDeskAgent, Userdata

# Charge les variables depuis le fichier .env (pour CAL_API_KEY)
load_dotenv()

TIMEZONE = "Europe/Paris"

def _llm_model() -> llm.LLM:
    return openai.LLM(model="gpt-4o", parallel_tool_calls=False, temperature=0.45)


# Marqueur pour ignorer ce test si la clé d'API n'est pas configurée
@pytest.mark.skipif(not os.getenv("CAL_API_KEY"), reason="CAL_API_KEY n'est pas définie, le test live est ignoré.")
@pytest.mark.asyncio
async def test_list_availability_live():
    """
    Teste la capacité de l'agent à lister les créneaux en utilisant la VRAIE API Cal.com.
    """
    # 1. Initialiser le vrai calendrier avec la clé d'API
    cal_api_key = os.getenv("CAL_API_KEY")
    cal = CalComCalendar(api_key=cal_api_key, timezone=TIMEZONE)
    await cal.initialize()

    userdata = Userdata(cal=cal)

    async with _llm_model() as llm, AgentSession(llm=llm, userdata=userdata) as session:
        await session.start(FrontDeskAgent(timezone=TIMEZONE))

        # 2. Simuler une demande utilisateur
        result = await session.run(user_input="Quelles sont vos disponibilités pour la semaine prochaine ?")

        # 4. Vérifier que l'agent envoie bien un message d'attente AVANT d'appeler l'outil
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(llm, intent="Informs the user that it is currently looking up information.")
        )

        # 5. Vérifier que l'appel à l'outil a bien lieu ensuite
        result.expect.next_event().is_function_call(name="list_available_slots")
        result.expect.next_event().is_function_call_output()  # La sortie sera les vrais créneaux de Cal.com

        # 4. Évaluer la réponse finale de l'agent
        # L'assertion est générale car on ne connaît pas les créneaux exacts à l'avance
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="Doit proposer à l'utilisateur quelques créneaux horaires disponibles et lui demander de faire un choix.",
            )
        )
