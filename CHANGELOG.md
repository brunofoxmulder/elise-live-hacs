# Changelog

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
