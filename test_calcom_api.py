#!/usr/bin/env python3
"""
Script de test pour vérifier l'API Cal.com directement
Usage: python test_calcom_api.py
"""

import asyncio
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import aiohttp

# Charger les variables d'environnement
load_dotenv()

BASE_URL = "https://api.cal.com/v2/"
CAL_COM_EVENT_TYPE = "livekit-front-desk"
EVENT_DURATION_MIN = 30

def build_headers(api_key: str, api_version: str = None) -> dict[str, str]:
    """Construire les headers pour l'API Cal.com"""
    h = {"Authorization": f"Bearer {api_key}"}
    if api_version:
        h["cal-api-version"] = api_version
    return h

async def test_calcom_api():
    """Test complet de l'API Cal.com"""
    
    # Vérifier la clé API
    cal_api_key = os.getenv("CAL_API_KEY")
    if not cal_api_key:
        print("❌ CAL_API_KEY n'est pas définie dans les variables d'environnement")
        return False
    
    print(f"🔑 CAL_API_KEY trouvée: {cal_api_key[:10]}...")
    print(f"🌐 Base URL: {BASE_URL}")
    
    async with aiohttp.ClientSession() as session:
        try:
            # Test 1: Vérifier l'authentification
            print("\n📡 Test 1: Vérification de l'authentification...")
            async with session.get(
                url=f"{BASE_URL}me/",
                headers=build_headers(cal_api_key, "2024-06-14")
            ) as resp:
                print(f"Status: {resp.status}")
                if resp.status == 200:
                    user_data = await resp.json()
                    print(f"✅ Authentification réussie!")
                    print(f"👤 Utilisateur: {user_data['data']['username']}")
                    username = user_data["data"]["username"]
                else:
                    error_text = await resp.text()
                    print(f"❌ Échec authentification: {resp.status}")
                    print(f"Erreur: {error_text}")
                    return False
            
            # Test 2: Lister les types d'événements
            print(f"\n📅 Test 2: Recherche du type d'événement '{CAL_COM_EVENT_TYPE}'...")
            from urllib.parse import urlencode
            query = urlencode({"username": username})
            async with session.get(
                url=f"{BASE_URL}event-types/?{query}",
                headers=build_headers(cal_api_key, "2024-06-14")
            ) as resp:
                print(f"Status: {resp.status}")
                if resp.status == 200:
                    event_types_data = await resp.json()
                    print(f"📋 Types d'événements trouvés: {len(event_types_data['data'])}")
                    
                    # Chercher notre type d'événement
                    lk_event_type = None
                    for event in event_types_data["data"]:
                        print(f"  - {event.get('slug', 'no-slug')}: {event.get('title', 'no-title')}")
                        if event.get("slug") == CAL_COM_EVENT_TYPE:
                            lk_event_type = event
                    
                    if lk_event_type:
                        event_type_id = lk_event_type["id"]
                        print(f"✅ Type d'événement trouvé: ID = {event_type_id}")
                    else:
                        print(f"⚠️  Type d'événement '{CAL_COM_EVENT_TYPE}' non trouvé")
                        print("🆕 Création du type d'événement...")
                        
                        create_payload = {
                            "lengthInMinutes": EVENT_DURATION_MIN,
                            "title": "LiveKit Front-Desk",
                            "slug": CAL_COM_EVENT_TYPE,
                        }
                        
                        async with session.post(
                            url=f"{BASE_URL}event-types",
                            headers=build_headers(cal_api_key, "2024-06-14"),
                            json=create_payload
                        ) as create_resp:
                            print(f"Create Status: {create_resp.status}")
                            if create_resp.status in [200, 201]:
                                create_data = await create_resp.json()
                                event_type_id = create_data["data"]["id"]
                                print(f"✅ Type d'événement créé: ID = {event_type_id}")
                            else:
                                error_text = await create_resp.text()
                                print(f"❌ Échec création: {create_resp.status}")
                                print(f"Erreur: {error_text}")
                                return False
                else:
                    error_text = await resp.text()
                    print(f"❌ Échec récupération types: {resp.status}")
                    print(f"Erreur: {error_text}")
                    return False
            
            # Test 3: Lister les créneaux disponibles
            print(f"\n🕐 Test 3: Récupération des créneaux disponibles...")
            tz = ZoneInfo("UTC")
            now = datetime.now(tz)
            end_time = now + timedelta(days=14)
            
            from urllib.parse import urlencode
            slots_query = urlencode({
                "eventTypeId": event_type_id,
                "start": now.isoformat(),
                "end": end_time.isoformat(),
            })
            
            async with session.get(
                url=f"{BASE_URL}slots/?{slots_query}",
                headers=build_headers(cal_api_key, "2024-09-04")
            ) as resp:
                print(f"Status: {resp.status}")
                if resp.status == 200:
                    slots_data = await resp.json()
                    print(f"📋 Données créneaux reçues")
                    
                    # Compter les créneaux
                    total_slots = 0
                    if "data" in slots_data:
                        for date, slots in slots_data["data"].items():
                            if isinstance(slots, list):
                                total_slots += len(slots)
                                print(f"  - {date}: {len(slots)} créneaux")
                    
                    print(f"✅ Total créneaux disponibles: {total_slots}")
                    
                    if total_slots > 0:
                        # Prendre le premier créneau pour test
                        first_date = list(slots_data["data"].keys())[0]
                        first_slot = slots_data["data"][first_date][0]
                        test_slot_time = first_slot["start"]
                        print(f"🎯 Créneau de test sélectionné: {test_slot_time}")
                        
                        # Test 4: Créer une réservation de test
                        print(f"\n📝 Test 4: Création d'une réservation de test...")
                        booking_payload = {
                            "start": test_slot_time,
                            "attendee": {
                                "name": "Test User",
                                "email": "test@example.com",
                                "timeZone": "UTC",
                            },
                            "eventTypeId": event_type_id,
                        }
                        
                        print(f"📋 Payload de réservation: {json.dumps(booking_payload, indent=2)}")
                        
                        async with session.post(
                            url=f"{BASE_URL}bookings",
                            headers=build_headers(cal_api_key, "2024-08-13"),
                            json=booking_payload
                        ) as booking_resp:
                            print(f"Booking Status: {booking_resp.status}")
                            booking_text = await booking_resp.text()
                            print(f"Response: {booking_text}")
                            
                            if booking_resp.status in [200, 201]:
                                try:
                                    booking_data = await booking_resp.json()
                                    print(f"✅ Réservation créée avec succès!")
                                    print(f"📋 Détails: {json.dumps(booking_data, indent=2)}")
                                except:
                                    print(f"✅ Réservation créée (réponse non-JSON)")
                            else:
                                print(f"❌ Échec création réservation: {booking_resp.status}")
                                try:
                                    error_data = await booking_resp.json()
                                    print(f"Erreur détaillée: {json.dumps(error_data, indent=2)}")
                                except:
                                    print(f"Erreur brute: {booking_text}")
                    else:
                        print("⚠️  Aucun créneau disponible pour test")
                        
                else:
                    error_text = await resp.text()
                    print(f"❌ Échec récupération créneaux: {resp.status}")
                    print(f"Erreur: {error_text}")
                    return False
            
            print(f"\n🎉 Tests terminés!")
            return True
            
        except Exception as e:
            print(f"💥 Erreur durant les tests: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    print("🧪 Test de l'API Cal.com")
    print("=" * 50)
    
    success = asyncio.run(test_calcom_api())
    
    if success:
        print("\n✅ Tous les tests ont réussi!")
    else:
        print("\n❌ Certains tests ont échoué.")