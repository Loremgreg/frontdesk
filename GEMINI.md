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
- **Connectivité Téléphonique :** Twilio (via SIP Trunk)
- **LLM (Cerveau) :** OpenAI `gpt-4o-mini`
- **STT (Transcription) :** Deepgram `nova-3` 
- **TTS (Voix) :** ElevenLabs `eleven_flash_v2_5`
- **VAD (Détection de voix) :** Silero VAD

## 3. Architecture & Lancement (SIP Trunking)

Cette section décrit l'architecture recommandée par LiveKit, basée sur SIP Trunking, et comment lancer l'application.

### Vue d'ensemble de l'architecture

Le système utilise une connexion directe entre Twilio et LiveKit, ce qui simplifie grandement le flux.

**Appel Téléphonique → Twilio (SIP Trunk) → LiveKit Cloud (Inbound Trunk & Dispatch Rule) → Agent IA**

1.  Un utilisateur appelle le numéro de téléphone Twilio.
2.  Twilio, via la configuration du **SIP Trunk**, transfère directement l'appel au **SIP Endpoint de LiveKit**.
3.  LiveKit reçoit l'appel sur son **Inbound Trunk**, qui vérifie que l'appel provient d'un numéro autorisé.
4.  Une **Dispatch Rule** est appliquée : elle crée une nouvelle chambre unique pour l'appel.
5.  LiveKit Cloud assigne un "job" à l'agent IA disponible, qui rejoint alors la chambre pour démarrer la conversation.

*Note : Avec cette architecture, le serveur local `twilio_server.py` et `ngrok` ne sont plus nécessaires pour les appels entrants.* 

### Configuration Requise (Unique)

Avant de pouvoir lancer l'agent, une configuration est nécessaire sur les plateformes externes :
1.  **Twilio :** Configurer un **Elastic SIP Trunk**, y attacher votre numéro de téléphone, et le pointer vers le **SIP Endpoint URI** de votre projet LiveKit.
2.  **LiveKit Cloud :** Dans la section "Telephony", créer un **Inbound Trunk** qui autorise les appels depuis votre numéro Twilio.
3.  **LiveKit Cloud :** Créer une **Dispatch Rule** qui prend les appels entrants et les place chacun dans une nouvelle chambre (ex: `dispatchRuleIndividual` avec un `roomPrefix`).

### Variables d'environnement

Créez un fichier `.env` à la racine du projet avec les variables suivantes :

```
# Clés API pour LiveKit (requises pour l'agent)
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

Une fois la configuration unique effectuée, le lancement est très simple.

**Terminal 1 : Lancer l'Agent IA**
L'agent se met en mode "worker" et attend les instructions de LiveKit Cloud.
```bash
python frontdesk_agent.py start
```
C'est tout. L'agent est maintenant prêt à recevoir des appels.

## 4. Documentation de Référence LiveKit

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
