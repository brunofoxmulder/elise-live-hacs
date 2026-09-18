# Élise Live

Intégration vocale Home Assistant pour **Gemini Live** et **OpenAI Realtime**, avec sélection de plusieurs API LLM Home Assistant.

**Version de test : 0.1.0-dev.3.** Ajoute le modèle stable `gemini-3.8-live` conformément aux recommandations de migration Google. La dev.2 reste le retour arrière validé pendant la recette terrain de cette candidate.

Variante indépendante de [ha-gemini-live](https://github.com/matt123p/ha-gemini-live), basée sur **v1.0.7**, sous licence MIT de Matt Pyne. Ce projet communautaire n'est affilié ni à Google, ni à OpenAI, ni à Home Assistant.

## Capacités

- Choisir plusieurs API LLM enregistrées dans Home Assistant, dans les options de l'intégration.
- Raccorder notamment **Tools for Assist** : Search Services et Weather Forecast, en plus d'Assist.
- Utiliser la fusion native Home Assistant des outils, schémas, instructions et appels.
- Préserver le contexte du pipeline vocal lorsqu'il est disponible sans ambiguïté. Une origine inconnue reste inconnue ; aucune identité humaine n'est inventée.
- Proposer `gemini-3.8-live` par défaut aux nouvelles entrées, tout en conservant Gemini 3.1 et 2.5 pour le repli.
- Appliquer le contrat Gemini 3.8 : sortie audio, aucun `thinking_level`, et appels d'outils bloquants jusqu'au résultat Home Assistant.
- Conserver le transport OpenAI de la base amont.

Le domaine `elise_live` permet de conserver `gemini_live` installé en parallèle. Les entrées, clés et assistants existants ne sont pas migrés automatiquement. Une sélection vide désactive les outils Home Assistant ; les callbacks de fin de conversation et d'affichage restent disponibles.

## Installation HACS

Prérequis : **Home Assistant 2026.9.2 ou plus récent**, HACS et une clé API du fournisseur choisi. Les tests de cette candidate ont été exécutés avec HA 2026.9.2 ; la compatibilité avec une version ultérieure reste à vérifier. Les outils de recherche et de météo nécessitent leurs intégrations configurées séparément.

1. Disposer d'une sauvegarde récente.
2. Dans **HACS → ⋮ → Dépôts personnalisés**, ajouter :

   ```text
   https://github.com/brunofoxmulder/elise-live-hacs
   ```

3. Choisir le type **Intégration**, puis télécharger **Élise Live**.
4. Redémarrer Home Assistant.
5. Dans **Paramètres → Appareils et services → Ajouter une intégration**, chercher **Élise Live**.
6. Choisir le fournisseur, saisir sa clé directement dans Home Assistant et sélectionner les API LLM souhaitées.
7. Créer un assistant de test séparé avec les nouvelles entités STT, conversation et TTS Élise Live.

Conserver l'assistant d'origine pendant les essais. Ce dépôt de distribution utilise sa branche par défaut ; le numéro de candidate est déclaré dans `manifest.json`.

## Validation et limites

53 tests hors production ont réussi sous Python 3.14.7 et Home Assistant 2026.9.2 (49 intégration, 4 installateur). Ils couvrent aussi le catalogue Gemini 3.8, sa capacité audio explicite, le mode d'outil `BLOCKING` accepté par le SDK et l'absence des paramètres Thinking non pris en charge. Le contrôle Tools for Assist emploie son code **1.10.2** inchangé ; seules les frontières réseau et données météo sont simulées. SDK : `google-genai==2.21.0`.

Ces résultats ne prouvent pas encore la connexion cloud, la qualité ou latence audio de Gemini 3.8, le choix d'outil par le modèle, ni une explication finale par un outil tiers. Le résolveur du contexte vocal dépend d'internes Home Assistant : si le contexte manque ou si plusieurs sessions sont ambiguës, l'appel reste anonyme.

Pour une recette : vérifier un véritable appel de recherche, une prévision météo, une commande simple autorisée, sa provenance, une relance vocale et le retour à l'assistant d'origine. Les mises à jour proposées dans HACS doivent être examinées avant installation.

## Origine et licence

Base amont : tag `v1.0.7`, commit `a5d71433060f6edc26bd15862aae3b2a1a7e98d6` de `matt123p/ha-gemini-live`. Le texte original de la licence MIT et son attribution sont conservés dans [LICENSE](LICENSE).
