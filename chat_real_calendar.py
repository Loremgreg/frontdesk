"""
Script interactif pour converser avec votre agent FrontDesk en utilisant le vrai calendrier Cal.com
"""

import os
import asyncio
import traceback
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from livekit.agents import AgentSession, llm
from livekit.plugins import openai

from calendar_api import CalComCalendar
from frontdesk_agent import FrontDeskAgent, Userdata

# Configurer le logging pour voir les erreurs détaillées
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat_real_calendar")

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
    
    # Utiliser les mêmes paramètres que dans entrypoint() de frontdesk_agent.py
    cal = CalComCalendar(api_key=cal_api_key, timezone=TIMEZONE)
    
    # Attendre explicitement l'initialisation du calendrier
    try:
        await cal.initialize()
        logger.info("Calendar initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing calendar: {e}")
        print(f"❌ Erreur d'initialisation du calendrier: {e}")
        return
    
    userdata = Userdata(cal=cal)
    
    # Créer une session avec les mêmes paramètres que dans entrypoint()
    async with _llm_model() as llm, AgentSession(
        llm=llm, 
        userdata=userdata,
        max_tool_steps=10,  # Paramètre crucial pour permettre plusieurs étapes d'outils
        preemptive_generation=True  # Correspond à la configuration dans entrypoint()
    ) as session:
        # Démarrer l'agent avec le même timezone que le calendrier
        agent = FrontDeskAgent(timezone=TIMEZONE)
        await session.start(agent)
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
                # Utiliser un timeout plus long pour permettre aux workflows de se terminer
                result = await asyncio.wait_for(
                    session.run(user_input=user_input), 
                    timeout=120  # 2 minutes devraient être suffisantes pour tous les workflows
                )
                
                # Affiche les événements du résultat et l'assistant
                if hasattr(result, "events"):
                    for ev in result.events:
                        # Logging brut pour debug
                        print(f"Event DEBUG: {ev}")
                        
                        # Capture et log les erreurs de fonction
                        if hasattr(ev, "type") and ev.type == "function_call_output":
                            if hasattr(ev.item, "is_error") and ev.item.is_error:
                                logger.error(f"Function error: {ev.item.output}")
                        
                        # Extraction du message réel
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
            except asyncio.TimeoutError:
                print("❌ Erreur: L'opération a pris trop de temps")
            except Exception as e:
                logger.error(f"Error during conversation: {e}")
                print(f"❌ Erreur: {e}")
                # Afficher la trace complète pour le débogage
                traceback.print_exc()

if __name__ == "__main__":
    # Utiliser un gestionnaire d'exceptions pour capturer les erreurs non gérées
    try:
        asyncio.run(chat_with_real_calendar())
    except KeyboardInterrupt:
        print("\n👋 Au revoir !")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        traceback.print_exc()
        print(f"❌ Erreur critique: {e}")