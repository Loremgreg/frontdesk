"""
Script interactif pour converser avec votre agent FrontDesk en utilisant le vrai calendrier Cal.com
"""

import os
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from livekit.agents import AgentSession, llm
from livekit.plugins import openai

from calendar_api import CalComCalendar
from frontdesk_agent import FrontDeskAgent, Userdata

TIMEZONE = "Europe/Paris"

def _llm_model() -> llm.LLM:
    return openai.LLM(model="gpt-4o", parallel_tool_calls=False, temperature=0.45)

async def chat_with_real_calendar():
    """Fonction principale pour la conversation interactive avec le vrai calendrier Cal.com"""
    
    print("🤖 Assistant FrontDesk - Conversation avec Cal.com")
    print("Tapez 'quit' ou 'exit' pour quitter")
    print("-" * 50)
    
    # Initialiser le vrai calendrier Cal.com
    cal_api_key = os.getenv("CAL_API_KEY")
    if not cal_api_key:
        print("❌ Erreur: CAL_API_KEY n'est pas définie dans les variables d'environnement")
        return
    
    cal = CalComCalendar(api_key=cal_api_key, timezone=TIMEZONE)
    await cal.initialize()
    
    userdata = Userdata(cal=cal)
    
    async with _llm_model() as llm, AgentSession(llm=llm, userdata=userdata) as session:
        # Aucune souscription d'événements : utilisation du debug dans le résultat de session.run()

        await session.start(FrontDeskAgent(timezone=TIMEZONE))
        print("✅ Calendrier Cal.com initialisé avec succès!")
        print("Vous pouvez maintenant discuter avec l'agent en utilisant vos vraies données Cal.com")
        while True:
            user_input = input("\n👤 Vous: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Au revoir !")
                break
            
            if not user_input:
                continue
            
            try:
                result = await session.run(user_input=user_input)
                # Affiche les événements du résultat et l'assistant
                if hasattr(result, "events"):
                    for ev in result.events:
                        # Logging brut pour debug
                        print(f"Event DEBUG: {ev}")
                        # Extraction du message réel (ChatMessageEvent.item ou ev.message)
                        msg = getattr(ev, "message", None) or getattr(ev, "item", None)
                        if msg:
                            role = getattr(msg, "role", None)
                            if role == "assistant":
                                content = getattr(msg, "content", None)
                                if isinstance(content, list) and content:
                                    text = content[0]
                                elif isinstance(content, str):
                                    text = content
                                else:
                                    text = str(content)
                                print(f"\n🤖 Agent: {text}")
            except Exception as e:
                print(f"❌ Erreur: {e}")

if __name__ == "__main__":
    asyncio.run(chat_with_real_calendar())





