# Directives pour le projet Voice-Assistant

Ce document fournit les instructions et le contexte nécessaires pour travailler sur ce projet d'assistant vocal.

## 1. Contexte du Projet

- **Objectif :** Créer un assistant vocal intelligent pour salons de coiffures. 
- **Fonctionnalités Clés :**
  1. **Accueil téléphonique automatique**  
     - Répondre aux appels entrants 24h/24 avec un message personnalisé.  
     - Identifier si l’appel concerne une prise de RDV ou une question générale.

  2. **Compréhension et réponse aux questions fréquentes**  
     - Répondre vocalement aux demandes courantes :  
       - Horaires d’ouverture  
       - Adresse du salon  
       - Tarifs (coupe, brushing, etc.)  
       - Disponibilités approximatives  
     - Utiliser une base de connaissances pré-remplie et personnalisable.

  3. **Prise de rendez-vous intelligente**  
     - Identifier le type de service demandé (ex : coupe, brushing, couleur).  
     - Proposer des créneaux disponibles (via Cal.com → Google Calendar).  
     - Confirmer vocalement et par SMS la date/heure choisie.  
     - Enregistrer le RDV dans l’agenda via l’API Cal.com.

  4. **Modification et annulation de rendez-vous**  
     - Permettre aux clients de déplacer ou annuler un RDV existant.  
     - Rechercher le RDV dans le calendrier par nom/date.  
     - Mettre à jour ou supprimer le RDV via API.

  5. **Confirmation & suivi automatique**  
     - Envoyer automatiquement un SMS (ou WhatsApp) de confirmation.  
     - Transcrire les demandes en texte et les envoyer par email (optionnel).
- **Persona de l'Agent :** Le ton doit toujours être professionnel, clair, concis et empathique.

## 2. Pile Technique

- **Langage :** Python
- **Framework d'Agent :** LiveKit Agents
- **Connectivité Téléphonique :** Twilio (Appels vocaux)
- **Serveur Webhook :** Flask + Hypercorn (serveur ASGI)
- **LLM (Cerveau) :** OpenAI `gpt-4o-mini`
- **STT (Transcription) :** Deepgram `nova-3` 
- **TTS (Voix) :** ElevenLabs `eleven_flash_v2_5`
- **VAD (Détection de voix) :** Silero VAD

## 3. Architecture & Lancement

Cette section décrit comment les différents services interagissent et comment lancer l'application en environnement de développement.

### Vue d'ensemble de l'architecture

Le système est composé de plusieurs services qui communiquent entre eux :

**Appel Téléphonique → Twilio → Ngrok → Serveur Webhook (Flask) → LiveKit Cloud → Agent IA**

1.  Un utilisateur appelle le numéro de téléphone Twilio.
2.  Twilio envoie une requête HTTP (webhook) à une URL publique fournie par Ngrok.
3.  Ngrok redirige cette requête vers le serveur Flask/Hypercorn qui tourne en local.
4.  Le serveur Flask crée une chambre LiveKit unique pour l'appel et renvoie une réponse TwiML à Twilio.
5.  Twilio connecte l'audio de l'appel à la chambre LiveKit via un flux WebSocket.
6.  LiveKit Cloud assigne un "job" à l'agent IA disponible, qui rejoint alors la chambre pour démarrer la conversation.

### Variables d'environnement

Créez un fichier `.env` à la racine du projet avec les variables suivantes :

```
# Clés API pour LiveKit (requises pour le serveur et l'agent)
LIVEKIT_API_KEY="votre_cle_api"
LIVEKIT_API_SECRET="votre_secret_api"
LIVEKIT_URL="wss://votre_url_livekit.livekit.cloud"

# Clé API pour le calendrier (ex: Cal.com)
CAL_API_KEY="votre_cle_calcom"

# Credentials pour les services de l'agent
OPENAI_API_KEY="..."
DEEPGRAM_API_KEY="..."
ELEVEN_API_KEY="..."

# Credentials Twilio (pour l'envoi de SMS de confirmation)
TWILIO_ACCOUNT_SID="..."
TWILIO_AUTH_TOKEN="..."
TWILIO_PHONE_NUMBER="..."
```

### Lancement en Développement

Pour tester l'application de bout en bout, vous devez lancer 3 processus distincts dans 3 terminaux.

**Terminal 1 : Lancer l'Agent IA**
L'agent se met en mode "worker" et attend les instructions de LiveKit Cloud.
```bash
python frontdesk_agent.py start
```

**Terminal 2 : Lancer le Serveur Webhook**
Ce serveur reçoit les requêtes de Twilio.
```bash
hypercorn twilio_server:app
```
*Note : Ce serveur écoute sur le port 8000 par défaut.*

**Terminal 3 : Lancer Ngrok**
Ngrok expose votre serveur local à Internet pour que Twilio puisse l'atteindre.
```bash
ngrok http 8000
```
*Attention : À chaque redémarrage de ngrok, l'URL publique change. Vous devez la mettre à jour dans la configuration de votre numéro sur la console Twilio.*

## 4. Diagramme de séquence — Appel vocal & Worker lifecycle (LiveKit/Twilio) 
[Client téléphone]
       |
       v
(Appel vocal)
       |
       v
[Numéro Twilio]
       |
       v
Webhook HTTP (TwiML)
       |
       v
[Ngrok - URL publique]
       |
       v
[Serveur Flask/Hypercorn]
  (crée une Room LiveKit)
       |
       v
[LiveKit Cloud]
  |       \
  |        \--> [Worker(s) enregistrés]  ← (Worker Registration)
  |                  |
  |         [Worker reçoit une Job Request]
  |                  |
  |         (Acceptation + Nouveau Processus)
  |                  |
  |         [Entrypoint() de l'agent]
  |                  |
  |        L'agent rejoint la Room
  |
(Twilio connecte audio → Room)
       |
       v
[Conversation temps réel]
       |
       v
Fin de session → (Worker revient standby)


sequenceDiagram
    autonumber
    participant Caller as Client (Téléphone)
    participant Twilio as Twilio (Numéro)
    participant Ngrok as Ngrok (URL publique)
    participant Webhook as Flask/Hypercorn (Webhook)
    participant LiveKit as LiveKit Cloud (Room)
    participant Worker as Worker Pool
    participant Agent as Agent Process (entrypoint)
    participant STT as Deepgram (STT)
    participant LLM as OpenAI (LLM)
    participant TTS as ElevenLabs (TTS)
    participant Cal as Cal.com API
    participant GCal as Google Calendar

    Caller->>Twilio: Appel entrant
    Twilio->>Ngrok: Webhook HTTP (TwiML)
    Ngrok->>Webhook: POST /voice
    Webhook->>LiveKit: Créer la Room (nom/metadata)
    Webhook-->>Twilio: Réponse TwiML (connecter l'audio)
    Twilio-->>LiveKit: Connecter l'audio (WebSocket/SIP) vers la Room

    Note over LiveKit,Worker: Worker lifecycle démarre ici (dispatch)
    LiveKit-->>Worker: JobRequest (agent requis pour la Room)
    Worker-->>LiveKit: Accept (ou reject)
    Worker->>Agent: Lancer un nouveau processus (prewarm appliqué si dispo)
    Agent->>LiveKit: Join Room (entrypoint)

    LiveKit-->>Agent: Flux audio du Caller
    Agent->>STT: Envoyer audio pour transcription (stream)
    STT-->>Agent: Texte (transcript)
    Agent->>LLM: Intent + policy + contexte (RAG éventuel)
    LLM-->>Agent: Réponse (plan d’action / texte)
    Agent->>Cal: Créer/mettre à jour/annuler RDV
    Cal-->>GCal: Sync (si configuré)
    Cal-->>Agent: OK + détails RDV
    Agent->>TTS: Synthèse réponse vocale
    TTS-->>LiveKit: Audio synthétisé
    LiveKit-->>Caller: Lecture de la réponse

    loop Tour de parole suivant
      Caller-->>LiveKit: Parle
      LiveKit-->>Agent: Audio
      Agent->>STT: Transcrire…
      STT-->>Agent: Texte
      Agent->>LLM: Décider/répondre
      LLM-->>Agent: Texte
      Agent->>TTS: Synthèse
      TTS-->>LiveKit: Audio
      LiveKit-->>Caller: Réponse
    end

    alt Fin d’appel / dernier non-agent quitte
      Agent->>LiveKit: ctx.shutdown(reason)
      LiveKit-->>Worker: Job terminé (processus se ferme)
    else Fin forcée (deleteRoom)
      Webhook/Backend->>LiveKit: deleteRoom()
      LiveKit-->>Worker: Job terminé
    end

```mermaid
flowchart TD
  Caller[Client téléphone]
  Twilio[Twilio - Numéro]
  Ngrok[Ngrok - URL publique]
  Flask[Serveur Flask/Hypercorn]
  LiveKit[LiveKit Cloud]
  WorkerPool[Workers enregistrés]
  Agent[Processus Agent (entrypoint)]
  STT[Deepgram - STT]
  LLM[OpenAI - LLM]
  TTS[ElevenLabs - TTS]
  Cal[Cal.com API]
  GCal[Google Calendar]
    Caller --> Twilio --> Ngrok --> Flask --> LiveKit
  Flask -. crée room .-> LiveKit
  LiveKit -->|dispatch job| WorkerPool -->|spawn process| Agent --> LiveKit
  Twilio -. connecte audio .-> LiveKit

  LiveKit --> Agent
  Agent --> STT --> Agent
  Agent --> LLM --> Agent
  Agent --> Cal --> GCal
  Agent --> TTS --> LiveKit --> Caller
```

## 5. Documentation de Référence LiveKit

En cas de doute sur le fonctionnement de LiveKit Agents, se référer en priorité à ces liens :

- **Introduction :** [https://docs.livekit.io/agents/](https://docs.livekit.io/agents/)
- **Playground :** [https://docs.livekit.io/agents/start/playground/](https://docs.livekit.io/agents/start/playground/)
- **Construction (Build) :** [https://docs.livekit.io/agents/build/](https://docs.livekit.io/agents/build/)
- **Workflows :** [https://docs.livekit.io/agents/build/workflows/](https://docs.livekit.io/agents/build/workflows/)
- **Audio & Parole :** [https://docs.livekit.io/agents/build/audio/](https://docs.livekit.io/agents/build/audio/)
- **Outils (Tools) :** [https://docs.livekit.io/agents/build/tools/](https://docs.livekit.io/agents/build/tools/)
- **Nodes & Hooks :** [https://docs.livekit.io/agents/build/nodes/](https://docs.livekit.io/agents/build/nodes/)
- **Détection de Tour (Turns) :** [https://docs.livekit.io/agents/build/turns/](https://docs.livekit.io/agents/build/turns/)
- **Données Externes & RAG :** [https://docs.livekit.io/agents/build/external-data/](https://docs.livekit.io/agents/build/external-data/)
- **Événements & Erreurs :** [https://docs.livekit.io/agents/build/events/](https://docs.livekit.io/agents/build/events/)
- **Cycle de vie du Worker :** [https://docs.livekit.io/agents/worker/](https://docs.livekit.io/agents/worker/)
- **OpenAI LLM integration guide :** [https://docs.livekit.io/agents/integrations/llm/openai/](https://docs.livekit.io/agents/integrations/llm/openai/)