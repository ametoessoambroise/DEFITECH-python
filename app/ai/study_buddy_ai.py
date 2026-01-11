"""
Module d'intégration de Gemini pour Study Buddy
Gère la génération de contenu éducatif (résumés, quiz, flashcards)
en utilisant l'API Gemini
"""

import json
import logging
from typing import Dict, List, Any

from app.services.gemini_integration import GeminiIntegration

logger = logging.getLogger(__name__)


class StudyBuddyAI:
    """Classe principale pour l'intégration de Gemini avec Study Buddy"""

    def __init__(self, api_key: str, model: str = "gemini-2.5-pro"):
        """
        Initialise le gestionnaire StudyBuddyAI avec la clé API Gemini

        Args:
            api_key: Clé d'API Gemini
            model: Modèle Gemini à utiliser (par défaut: gemini-2.5-pro)
        """
        self.gemini = GeminiIntegration(api_key=api_key, model=model)
        self.max_retries = 3

    def generate_summary(
        self, document_text: str, level: str = "intermediate"
    ) -> Dict[str, Any]:
        """
        Génère un résumé du document avec un niveau de détail spécifique

        Args:
            document_text: Texte du document à résumer
            level: Niveau de détail ('beginner', 'intermediate', 'advanced')

        Returns:
            Dictionnaire contenant le résumé et les points clés
        """
        level_instructions = {
            "beginner": """
            Crée un résumé très simple et accessible pour un débutant.
            - Utilise un langage simple et des explications claires
            - Définis les termes techniques
            - Donne des exemples concrets
            - Structure en sections courtes avec des titres clairs
            """,
            "intermediate": """
            Crée un résumé détaillé pour un public avec des connaissances de base.
            - Structure avec une introduction, développement et conclusion
            - Inclus les concepts clés avec des explications
            - Utilise des exemples pertinents
            - Mets en avant les relations entre les concepts
            """,
            "advanced": """
            Crée un résumé technique et approfondi pour un public expert.
            - Va droit à l'essentiel avec des termes techniques précis
            - Inclus des détails spécifiques et des nuances
            - Mentionne les débats ou controverses dans le domaine
            - Propose des références pour approfondir
            """,
        }

        prompt = f"""
        Tu es un assistant éducatif expert dans la création de résumés de cours.
        {level_instructions.get(level, level_instructions['intermediate'])}
        
        Voici le contenu du document à résumer :
        ---
        {document_text[:15000]}  # Limite pour éviter les tokens excessifs
        ---
        
        Génère un résumé structuré au format JSON avec les champs suivants :
        - title: Titre du résumé
        - overview: Aperçu général (2-3 phrases)
        - key_points: Liste des points clés (5-7 points)
        - detailed_summary: Résumé détaillé structuré
        - key_terms: Liste des termes clés avec définitions
        """

        try:
            # Appel à l'API Gemini
            response = self.gemini.generate_response(
                prompt=prompt,
                temperature=0.3 if level == "advanced" else 0.5,
            )

            # Journalisation de la réponse brute pour le débogage
            logger.debug(f"Réponse brute de l'API: {response}")

            # Vérifier si la réponse est valide
            if not isinstance(response, dict):
                logger.error(f"Réponse invalide de l'API: {response}")
                raise ValueError("Format de réponse inattendu de l'API Gemini")

            if not response.get("success", False):
                error_msg = response.get("error", "Erreur inconnue de l'API Gemini")
                logger.error(f"Erreur de l'API Gemini: {error_msg}")
                raise ValueError(f"Erreur de l'API Gemini: {error_msg}")

            # Récupérer le texte de la réponse
            response_text = response.get("response", "")
            if not response_text:
                logger.error("Réponse vide de l'API Gemini")
                raise ValueError("Réponse vide de l'API Gemini")

            # Nettoyer la réponse (supprimer les marqueurs de code markdown)
            clean_text = response_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

            # Essayer de parser la réponse en JSON
            try:
                summary = json.loads(clean_text)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Échec du parsing JSON, tentative d'extraction du texte brut: {e}"
                )
                # Si le parsing JSON échoue, retourner le texte brut comme résumé
                summary = {
                    "title": "Résumé du document",
                    "overview": (
                        clean_text[:500]
                        if clean_text
                        else "Aucun contenu dans la réponse"
                    ),
                    "key_points": ["Le contenu n'a pas pu être analysé comme prévu"],
                    "detailed_summary": clean_text,
                    "key_terms": [],
                }

            # Vérifier que le résumé a la structure attendue
            if not isinstance(summary, dict):
                raise ValueError("La réponse n'est pas un objet JSON valide")

            # S'assurer que tous les champs requis sont présents
            required_fields = [
                "title",
                "overview",
                "key_points",
                "detailed_summary",
                "key_terms",
            ]
            for field in required_fields:
                if field not in summary:
                    logger.warning(f"Champ manquant dans la réponse: {field}")
                    summary[field] = "" if field != "key_points" else []

            return summary

        except Exception as e:
            logger.error(
                f"Erreur lors de la génération du résumé: {str(e)}", exc_info=True
            )
            # Retourner une réponse d'erreur structurée
            return {
                "title": "Erreur lors de la génération du résumé",
                "overview": f"Une erreur est survenue : {str(e)[:200]}",
                "key_points": [
                    "Erreur lors de la génération du résumé",
                    "Veuillez réessayer ou contacter le support si le problème persiste",
                ],
                "detailed_summary": f"Erreur détaillée : {str(e)}\n\nRéponse de l'API : {response_text if 'response_text' in locals() else 'Non disponible'}",
                "key_terms": [],
            }

    def generate_quiz_questions(
        self, document_text: str, num_questions: int = 5, difficulty: str = "medium"
    ) -> List[Dict[str, Any]]:
        """
        Génère des questions de quiz à partir du texte du document

        Args:
            document_text: Texte du document source
            num_questions: Nombre de questions à générer (1-10)
            difficulty: Niveau de difficulté ('easy', 'medium', 'hard')

        Returns:
            Liste de dictionnaires contenant les questions et réponses
        """
        # Valider les entrées
        num_questions = max(1, min(10, int(num_questions)))

        prompt = f"""
        Tu es un expert en création de questions d'évaluation éducative.
        
        Tâche : Crée {num_questions} questions de type QCM (4 options) basées sur le texte fourni.
        Niveau de difficulté : {difficulty}
        
        Instructions spécifiques :
        1. Les questions doivent tester la compréhension des concepts clés
        2. Une seule réponse correcte par question
        3. Les mauvaises réponses doivent être plausibles
        4. Inclus une explication pour chaque réponse correcte
        5. Le format de sortie doit être du JSON valide
        
        Format de sortie attendu :
        [
          {{
            "question": "Texte de la question",
            "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
            "correct_index": 0,
            "explanation": "Explication de la réponse correcte",
            "difficulty": "{difficulty}",
            "tags": ["tag1", "tag2"]
          }},
          ...
        ]
        
        Texte source :
        ---
        {document_text[:10000]}  # Limiter la taille pour éviter les dépassements
        ---
        """

        response = self.gemini.generate_response(
            prompt=prompt,
            temperature=0.7,
        )

        try:
            questions = json.loads(response.get("text", "[]"))
            if not isinstance(questions, list):
                raise ValueError("La réponse doit être une liste de questions")
            return questions[
                :num_questions
            ]  # S'assurer de ne pas dépasser le nombre demandé
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Erreur lors de la génération du quiz: {e}")
            return []

    def generate_flashcards(
        self, document_text: str, num_cards: int = 10
    ) -> List[Dict[str, str]]:
        """
        Génère des cartes mémoire à partir du texte du document

        Args:
            document_text: Texte du document source
            num_cards: Nombre de cartes à générer (1-20)

        Returns:
            Liste de dictionnaires contenant les cartes mémoire (front, back)
        """
        num_cards = max(1, min(20, int(num_cards)))

        prompt = f"""
        Tu es un expert en création de cartes mémoire éducatives (flashcards).
        
        Tâche : Crée {num_cards} paires de cartes mémoire basées sur le texte fourni.
        
        Instructions :
        1. Identifie les concepts clés et leurs définitions/explications
        2. Pour chaque concept, crée une carte avec :
           - Face avant (question/terme) : claire et concise
           - Face arrière (réponse) : explication complète mais brève
        3. Les cartes doivent être indépendantes les unes des autres
        4. Le format de sortie doit être du JSON valide
        
        Format de sortie attendu :
        [
          {{
            "front": "Question ou terme",
            "back": "Réponse ou définition",
            "tags": ["tag1", "tag2"]
          }},
          ...
        ]
        
        Texte source :
        ---
        {document_text[:8000]}  # Limiter la taille pour éviter les dépassements
        ---
        """

        response = self.gemini.generate_response(
            prompt=prompt,
            temperature=0.5,
        )

        try:
            cards = json.loads(response.get("text", "[]"))
            if not isinstance(cards, list):
                raise ValueError("La réponse doit être une liste de cartes")
            return cards[:num_cards]
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Erreur lors de la génération des flashcards: {e}")
            return []

    def analyze_document_structure(self, document_text: str) -> Dict[str, Any]:
        """
        Analyse la structure d'un document pour en extraire les sections clés

        Args:
            document_text: Texte du document à analyser

        Returns:
            Dictionnaire contenant la structure analysée
        """
        prompt = f"""
        Analyse la structure du document suivant et identifie les sections clés.
        
        Pour chaque section, fournis :
        - Un titre court
        - Un résumé en une phrase
        - Les concepts clés
        - La difficulté estimée (débutant, intermédiaire, avancé)
        
        Format de sortie attendu (JSON) :
        {{
          "title": "Titre du document",
          "sections": [
            {{
              "title": "Titre de la section",
              "summary": "Résumé en une phrase",
              "key_concepts": ["concept1", "concept2"],
              "difficulty": "niveau"
            }}
          ],
          "total_sections": 5,
          "estimated_study_time": "X minutes"
        }}
        
        Document à analyser :
        ---
        {document_text[:12000]}
        ---
        """

        response = self.gemini.generate_response(
            prompt=prompt,
            temperature=0.3,  # Basse température pour plus de cohérence
        )

        try:
            structure = json.loads(response.get("text", "{}"))
            if not isinstance(structure, dict):
                raise ValueError("La réponse n'est pas un objet JSON valide")
            return structure
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Erreur lors de l'analyse de la structure: {e}")
            return {
                "error": "Impossible d'analyser la structure du document",
                "details": str(e),
            }

    def generate_study_plan(
        self, document_structure: Dict[str, Any], available_hours: float = 10.0
    ) -> Dict[str, Any]:
        """
        Génère un plan d'étude personnalisé basé sur la structure du document

        Args:
            document_structure: Structure du document (issue de analyze_document_structure)
            available_hours: Nombre d'heures disponibles pour l'étude

        Returns:
            Dictionnaire contenant le plan d'étude
        """
        prompt = f"""
        En tant qu'expert en méthodes d'apprentissage, crée un plan d'étude personnalisé
        basé sur la structure de document fournie.
        
        Structure du document :
        {json.dumps(document_structure, indent=2, ensure_ascii=False)}
        
        Temps disponible : {available_hours} heures
        
        Crée un plan d'étude qui :
        1. Répartit le temps de manière proportionnelle à la difficulté et à l'importance
        2. Alterne entre les sections pour maintenir l'intérêt
        3. Inclut des sessions de révision espacées
        4. Propose des objectifs clairs pour chaque session
        
        Format de sortie attendu (JSON) :
        {{
          "total_hours": {available_hours},
          "sessions": [
            {{
              "session_number": 1,
              "duration_minutes": 45,
              "focus_areas": ["section1", "section2"],
              "objectives": ["objectif 1", "objectif 2"],
              "study_techniques": ["technique1", "technique2"],
              "materials_needed": ["matériel1", "matériel2"]
            }}
          ],
          "recommended_schedule": [
            {{
              "day": "Lundi",
              "sessions": [1, 2],
              "total_time_minutes": 90
            }}
          ]
        }}
        """

        response = self.gemini.generate_response(
            prompt=prompt,
            temperature=0.4,  # Température modérée pour un équilibre créativité/cohérence
        )

        try:
            study_plan = json.loads(response.get("text", "{}"))
            if not isinstance(study_plan, dict):
                raise ValueError("La réponse n'est pas un objet JSON valide")
            return study_plan
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Erreur lors de la génération du plan d'étude: {e}")
            return {"error": "Impossible de générer un plan d'étude", "details": str(e)}
