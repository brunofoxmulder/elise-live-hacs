# Changelog

## 0.1.0-dev.4 — 2026-09-19

- Ajoute un pont local fail-safe vers l’App Élise Memory sur le réseau interne Home Assistant.
- Expose l’outil `elise_memory_search` aux chemins vocal et texte pour interroger la mémoire SQLite sans charger toute la base dans le contexte.
- Charge une fois par conversation le contexte temporel `/v1/session/open` et demande le salut de réveil uniquement pour la première conversation du cycle.
- Confirme le salut à Élise Memory seulement après avoir observé dans la transcription la formule attendue, puis appelle `/v1/session/greeting/commit`.
- Préserve les chemins existants Home Assistant, Investigator et fournisseurs Live ; une panne d’Élise Memory reste non bloquante.
- Validation CI ajoutée ; recette Home Assistant réelle requise avant de considérer dev.4 validée terrain.

## 0.1.0-dev.3 — 2026-09-18

- Ajoute le modèle stable `gemini-3.8-live`, par défaut uniquement pour les nouvelles configurations ; les entrées existantes gardent leur modèle.
- N'envoie aucun `thinking_level` ni `thinking_config`, conformément au guide Google.
- Déclare les outils Gemini 3.8 en mode `BLOCKING` pour attendre le résultat Home Assistant avant la réponse.
- Remplace la détection audio fondée sur le nom du modèle par des capacités explicites ; conserve Gemini 3.1/2.5 et OpenAI.
- 53 tests hors production réussis ; recette cloud et audio réelle encore requise.

## 0.1.0-dev.2 — 2026-09-18

- Corrige l'échec Gemini avec Weather Forecast et les autres outils retournant du texte, une liste ou une valeur simple. Le résultat est transmis comme objet JSON, commun aux chemins vocal et écrit.
- Préserve les réponses structurées, les erreurs et les identifiants d'appels.
- Tests du vrai SDK Google et du retour Tools for Assist ajoutés ; 49 tests hors production réussis (45 intégration, 4 installateur).
- Recette sur l'installation cible toujours requise après mise à jour.

## 0.1.0-dev.1 — 2026-09-18

Première candidate de test dérivée de ha-gemini-live v1.0.7 (MIT).

- Domaine et événements `elise_live` distincts de l'intégration amont.
- Sélection multiple des API LLM et fusion native Home Assistant pour les chemins texte et audio.
- Compatibilité hors ligne vérifiée avec les groupes Search Services et Weather Forecast de Tools for Assist 1.10.2.
- Conservation du contexte vocal authentique lorsqu'il peut être identifié sans ambiguïté.
- Interface de configuration en français et en anglais.
- 35 tests hors production réussis. Validation terrain requise.
