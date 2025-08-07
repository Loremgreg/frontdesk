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

## 2. Pile Technique Principale

- **Langage :** Python
- **Framework d'Agent :** LiveKit Agents
- **LLM (Cerveau) :** OpenAI `gpt-4o-mini`
- **STT (Transcription) :** Deepgram `nova-3` 
- **TTS (Voix) :** ElevenLabs `eleven_flash_v2_5`
- **VAD (Détection de voix) :** Silero VAD


## 3. Documentation de Référence LiveKit
- **Utilise /mcp context7"" : parcours la librairie de Livekit en utilisant le mcp context7

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
- **OpenAI LLM integration guide :** [https://docs.livekit.io/agents/integrations/llm/openai/]
(https://docs.livekit.io/agents/integrations/llm/openai/)


