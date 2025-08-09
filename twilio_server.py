import os
import uuid
from dotenv import load_dotenv
from quart import Quart, request, Response
from twilio.twiml.voice_response import VoiceResponse, Connect
from livekit.api import LiveKitAPI, CreateRoomRequest, AccessToken, VideoGrants

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

app = Quart(__name__)

# Récupérer les credentials LiveKit depuis l'environnement
livekit_api_key = os.environ.get("LIVEKIT_API_KEY")
livekit_api_secret = os.environ.get("LIVEKIT_API_SECRET")
livekit_url = os.environ.get("LIVEKIT_URL")

# S'assurer que les credentials sont bien chargées
if not all([livekit_api_key, livekit_api_secret, livekit_url]):
    raise EnvironmentError("LIVEKIT_API_KEY, LIVEKIT_API_SECRET, et LIVEKIT_URL doivent être définis")

# Le client LiveKit sera initialisé dans les routes asynchrones

@app.route("/voice", methods=["POST"])
async def voice():
    # Créer un nom de chambre unique pour chaque appel
    room_name = str(uuid.uuid4())
    
    # Créer une identité pour le participant (l'appelant Twilio)
    participant_identity = f"twilio-caller-{request.form.get('CallSid')}"

    try:
        # Créer une instance de LiveKitAPI (lit automatiquement les variables d'environnement)
        async with LiveKitAPI() as lkapi:
            # 1. Créer la chambre sur LiveKit
            await lkapi.room.create_room(CreateRoomRequest(name=room_name))

            # 2. Créer un jeton d'accès pour que Twilio puisse rejoindre cette chambre
            token = (
                AccessToken(livekit_api_key, livekit_api_secret)
                .with_identity(participant_identity)
                .with_name("Twilio Caller")
                .with_grants(VideoGrants(room_join=True, room=room_name))
                .to_jwt()
            )

            # 3. Construire la réponse TwiML pour connecter l'appel à la chambre LiveKit
            response = VoiceResponse()
            connect = Connect()
            # L'URL du stream doit contenir le jeton d'accès
            connect.stream(url=f"{livekit_url.replace('http', 'ws')}", access_token=token)
            response.append(connect)

            print(f"Appel entrant. Chambre créée: {room_name}, Jeton généré pour: {participant_identity}")

            return Response(str(response), mimetype="text/xml")

    except Exception as e:
        print(f"Erreur lors de la création de la chambre ou du jeton: {e}")
        response = VoiceResponse()
        response.say("Désolé, une erreur technique est survenue. Veuillez réessayer plus tard.", language="fr-FR")
        return Response(str(response), mimetype="text/xml")

@app.route("/sms", methods=["POST"])
def sms():
    print("SMS reçu :", request.form)
    return Response("<Response></Response>", mimetype="text/xml")

if __name__ == "__main__":
    # Assurez-vous que le worker de l'agent est déjà lancé avant de démarrer ce serveur
    print("Lancement du serveur Twilio sur le port 8000...")
    print("Assurez-vous que votre agent LiveKit est en cours d'exécution.")
    app.run(port=8000)
