# Standard library imports
import json
import logging
import os
import chardet
from datetime import datetime, timedelta
from typing import Optional
from PyPDF2 import PdfReader

# Third-party imports
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
    send_from_directory,
)
import io
import requests
from flask_login import current_user, login_required

# Local application imports
from app.extensions import db
from app.models.flashcard import Flashcard, FlashcardStatus
from app.models.quiz_models import (
    Question,
    Quiz,
    QuizAnswer,
    QuizAttempt,
)
from app.models.study_document import StudyDocument
from app.models.study_progress import StudyProgress
from app.models.study_session import StudySession
from app.routes.ai_assistant import gemini

# Configuration du logging
logger = logging.getLogger(__name__)

# Configuration
UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "uploads",
    "study_documents",
)
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "pptx", "md"}

# Création du Blueprint
study_buddy_bp = Blueprint("study_buddy", __name__, url_prefix="/study-buddy")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def detect_buffer_encoding(data, default_encoding="utf-8"):
    """Détecte l'encodage de données binaires."""
    encodings_to_try = [
        "utf-8",
        "latin-1",
        "windows-1252",
        "iso-8859-15",
        "cp1252",
        "utf-16",
    ]

    try:
        result = chardet.detect(data[:10000])
        if result and result["confidence"] > 0.7:
            return result["encoding"].lower()
    except Exception as e:
        logger.error("Erreur ", e)

    for encoding in encodings_to_try:
        try:
            data[:1024].decode(encoding)
            return encoding
        except Exception as e:
            logger.error("Erreur ", e)

    return default_encoding


def extract_text_from_buffer(buffer: io.BytesIO, file_type: str) -> Optional[str]:
    """Extrait le texte d'un buffer selon le type de fichier."""
    content = ""
    try:
        if file_type.lower() == "pdf":
            pdf_reader = PdfReader(buffer)
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    content += page_text + "\n\n"
        else:
            data = buffer.getvalue()
            encoding = detect_buffer_encoding(data)
            content = data.decode(encoding, errors="replace")
        return content.strip()
    except Exception as e:
        logger.error(f"Erreur d'extraction de texte ({file_type}): {e}")
        return None


def get_document_buffer(document: StudyDocument) -> Optional[io.BytesIO]:
    """Récupère le contenu d'un document (local ou distant) et retourne un buffer."""
    if document.file_path.startswith(("http://", "https://")):
        try:
            logger.info(f"Tentative de téléchargement depuis URL: {document.file_path}")
            response = requests.get(document.file_path, timeout=10)
            if response.status_code == 200:
                logger.info(
                    f"Téléchargement réussi pour doc {document.id}. Taille: {len(response.content)} bytes"
                )
                return io.BytesIO(response.content)
            else:
                logger.error(
                    f"Échec téléchargement HTTP {response.status_code} pour doc {document.id}"
                )
                return None
        except Exception as e:
            logger.error(
                f"Erreur lors du téléchargement du document {document.id} depuis {document.file_path}: {e}"
            )
            return None
    else:
        if os.path.exists(document.file_path):
            with open(document.file_path, "rb") as f:
                return io.BytesIO(f.read())
    return None


@study_buddy_bp.route("/")
@login_required
def index():
    """
    Page d'accueil de Study Buddy.

    Cette fonction est le point d'entrée principal de l'application Study Buddy.
    Elle permet à l'utilisateur de se connecter et d'accéder à la page d'accueil.

    Retourne :
        Une réponse HTML contenant la page d'accueil de Study Buddy.
    """
    recent_documents = (
        StudyDocument.query.filter_by(user_id=current_user.id)
        .order_by(StudyDocument.updated_at.desc())
        .limit(5)
        .all()
    )

    # Récupérer la progression de l'utilisateur
    progress = StudyProgress.query.filter_by(user_id=current_user.id).first()

    # Si pas de progression, en créer une nouvelle
    if not progress:
        progress = StudyProgress(user_id=current_user.id)
        db.session.add(progress)
        db.session.commit()

    # Récupérer les sessions d'étude récentes
    recent_sessions = (
        StudySession.query.filter_by(user_id=current_user.id)
        .order_by(StudySession.start_time.desc())
        .limit(3)
        .all()
    )

    # Récupérer les cartes mémoire à réviser
    due_flashcards = (
        Flashcard.query.filter(
            Flashcard.user_id == current_user.id,
            (Flashcard.due_date <= datetime.utcnow()) | (Flashcard.due_date.is_(None)),
        )
        .limit(10)
        .all()
    )

    return render_template(
        "study_buddy/index.html",
        recent_documents=recent_documents,
        progress=progress,
        recent_sessions=recent_sessions,
        due_flashcards=due_flashcards,
    )


@study_buddy_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload_document():
    """
    Téléverser un nouveau document d'étude.

    Cette fonction est utilisée pour permettre à un utilisateur de téléverser un nouveau document
    d'étude. Lorsque la requête est GET, la fonction renvoie une réponse HTML contenant un formulaire
    permettant au utilisateur de sélectionner un fichier. Lorsque la requête est POST, la fonction
    vérifie que le fichier sélectionné est valide (d'après une liste blanche d'extensions de fichiers),
    puis le sauvegarde dans le dossier de téléchargement défini par la variable UPLOAD_FOLDER. Un
    nouvel enregistrement de document est ensuite créé dans la base de données, contenant des métadonnées
    telles que le nom du fichier, le chemin du fichier, le type de fichier, la taille du fichier,
    et l'utilisateur propriétaire du document.

    Retourne :
        Une réponse HTML contenant un formulaire permettant au utilisateur de sélectionner un fichier.
        Si la requête est POST, renvoie une redirection vers la page d'accueil.
    """
    if request.method == "POST":
        # Valider si un fichier est présent
        if "file" not in request.files:
            flash("Aucun fichier sélectionné.", "error")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            flash("Aucun fichier sélectionné.", "error")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Type de fichier non autorisé.", "error")
            return redirect(request.url)

        try:
            from app.utils.cloudinary_utils import upload_to_cloudinary

            # Upload to Cloudinary
            upload_result = upload_to_cloudinary(
                file, file.filename, folder="study_documents", resource_type="raw"
            )

            # Extract metadata from result
            file_url = upload_result.get("secure_url")
            file_size = upload_result.get("bytes", 0)
            file_format = upload_result.get("format")
            if not file_format and "." in file.filename:
                file_format = file.filename.rsplit(".", 1)[1].lower()

            # Créer un nouvel enregistrement de document avec l'URL Cloudinary
            description = request.form.get("description", "")
            document = StudyDocument(
                user_id=current_user.id,
                title=request.form.get("title") or os.path.splitext(file.filename)[0],
                file_name=file.filename,
                file_path=file_url,  # URL Cloudinary
                file_type=file_format,
                file_size=int(file_size),
                # Stocker la description dans les métadonnées car la colonne n'existe pas
                content_metadata={"description": description} if description else None,
            )
            # Note: Le modèle peut avoir d'autres champs non gérés ici, mais on se concentre sur l'essentiel

            db.session.add(document)

            # Mettre à jour les statistiques de progression
            progress = StudyProgress.query.filter_by(user_id=current_user.id).first()
            if not progress:
                progress = StudyProgress(user_id=current_user.id)
                db.session.add(progress)

            progress.total_documents += 1

            db.session.commit()

            flash("Document ajouté avec succès !", "success")
            return redirect(
                url_for("study_buddy.document_detail", document_id=document.id)
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur lors de l'ajout du document: {str(e)}")
            flash(f"Erreur lors de l'ajout du document: {str(e)}", "error")
            return redirect(request.url)

    # Récupérer ou créer la progression de l'utilisateur
    progress = StudyProgress.query.filter_by(user_id=current_user.id).first()
    if not progress:
        progress = StudyProgress(user_id=current_user.id)
        db.session.add(progress)
        db.session.commit()

    return render_template("study_buddy/upload.html", progress=progress)


@study_buddy_bp.route("/documents/<int:document_id>")
@login_required
def document_detail(document_id):
    """
    Affiche les détails d'un document et ses fonctionnalités.

    Args:
        document_id (int): Identifiant unique du document à afficher.

    Raises:
        NotFound: Si le document demandé n'existe pas.

    Returns:
        Render de la page "study_buddy/document_detail.html" avec les détails du document
        et ses fonctionnalités.
    """
    document = StudyDocument.query.get_or_404(document_id)

    # Vérifier que l'utilisateur est autorisé à voir ce document
    if document.user_id != current_user.id:
        flash("Accès non autorisé", "error")
        return redirect(url_for("study_buddy.index"))

    # Ajouter une variable pour indiquer si l'utilisateur est l'auteur
    is_author = document.user_id == current_user.id

    # Récupérer les sessions liées à ce document
    sessions = (
        StudySession.query.filter_by(user_id=current_user.id, document_id=document_id)
        .order_by(StudySession.start_time.desc())
        .limit(5)
        .all()
    )

    # Récupérer les quiz liés à ce document
    quizzes = (
        Quiz.query.filter_by(user_id=current_user.id, document_id=document_id)
        .order_by(Quiz.created_at.desc())
        .all()
    )

    # Récupérer les cartes mémoire liées à ce document
    flashcards = (
        Flashcard.query.filter_by(user_id=current_user.id, document_id=document_id)
        .order_by(Flashcard.created_at.desc())
        .limit(10)
        .all()
    )

    progress = StudyProgress.query.filter_by(user_id=current_user.id).first()

    if not progress:
        progress = StudyProgress(user_id=current_user.id)
        db.session.add(progress)
        db.session.commit()

    return render_template(
        "study_buddy/document_detail.html",
        document=document,
        sessions=sessions,
        quizzes=quizzes,
        flashcards=flashcards,
        progress=progress,
        is_author=is_author,
    )


@study_buddy_bp.route("/documents/<int:document_id>/download")
@login_required
def download_document(document_id):
    """
    Télécharger un document.

    Cette fonction est utilisée pour permettre à un utilisateur de télécharger un document.
    Elle vérifie d'abord si l'utilisateur est autorisé à télécharger ce document (c'est-à-dire
    s'il en est l'auteur). Ensuite, elle vérifie si le fichier du document existe encore sur le
    serveur. Si tout est ok, elle renvoie le fichier au client.

    Args:
        document_id (int): L'identifiant du document à télécharger.

    Retourne :
        Renvoie le fichier demandé au client.
    """
    document = StudyDocument.query.get_or_404(document_id)
    # Vérifier que l'utilisateur est autorisé à télécharger ce document
    if document.user_id != current_user.id:
        flash("Accès non autorisé", "error")
        return redirect(url_for("study_buddy.index"))

    if document.file_path.startswith(("http://", "https://")):
        # Rediriger vers l'URL Cloudinary (avec flags de téléchargement si possible, sinon direct)
        return redirect(document.file_path)

    if not os.path.exists(document.file_path):
        flash("Le fichier demandé n'existe plus sur le serveur.", "error")
        return redirect(url_for("study_buddy.document_detail", document_id=document.id))
    # Envoyer le fichier pour téléchargement
    return send_from_directory(
        os.path.dirname(document.file_path),
        os.path.basename(document.file_path),
        as_attachment=True,
        download_name=document.file_name,
    )


@study_buddy_bp.route("/documents/<int:document_id>/summarize", methods=["POST"])
@login_required
def generate_summary(document_id):
    """
    Génère un résumé du document avec Gemini.

    Cette fonction est utilisée pour générer un résumé d'un document en utilisant l'intégration
    Gemini. Elle vérifie d'abord si l'utilisateur est autorisé à générer un résumé de ce document
    (c'est-à-dire s'il en est l'auteur). Ensuite, elle vérifie si le fichier du document existe
    encore sur le serveur. Si tout est ok, elle utilise l'intégration Gemini pour générer un
    résumé du document et le renvoie au client.

    Args:
        document_id (int): L'identifiant du document à générer.

    Retourne :
        Renvoie un résumé du document au format JSON.
    """
    document = StudyDocument.query.get_or_404(document_id)

    # Vérifier que l'utilisateur est autorisé
    if document.user_id != current_user.id:
        return jsonify({"error": "Accès non autorisé"}), 403

    # Récupérer le niveau de détail demandé
    level = request.json.get("level", "intermediate")

    # Récupérer le contenu du document
    try:
        buffer = get_document_buffer(document)
    except Exception as e:
        return (
            jsonify({"error": f"Erreur lors de la récupération du document: {str(e)}"}),
            500,
        )

    if not buffer:
        return jsonify({"error": "Impossible de récupérer le contenu du document"}), 404

    content = extract_text_from_buffer(buffer, document.file_type)
    if not content:
        return jsonify({"error": "Impossible d'extraire le texte du document"}), 400

    try:

        # Enregistrer une nouvelle session d'étude
        session = StudySession(
            user_id=current_user.id,
            document_id=document_id,
            session_type=f"summary_{level}",
        )
        db.session.add(session)

        # Mettre à jour la progression
        progress = StudyProgress.query.filter_by(user_id=current_user.id).first()
        if not progress:
            progress = StudyProgress(user_id=current_user.id)
            db.session.add(progress)

        # Mettre à jour le temps d'étude total
        progress.total_study_time_seconds = (
            progress.total_study_time_seconds or 0
        ) + 300  # 5 minutes en secondes
        progress.updated_at = datetime.utcnow()
        db.session.commit()

        # Générer le résumé avec Gemini
        summary = current_app.study_buddy_ai.generate_summary(
            document_text=content, level=level
        )

        # Mettre à jour le document avec le résumé généré
        document.summary = json.dumps(summary)
        document.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify(summary)

    except Exception as e:
        logger.error(f"Erreur lors de la génération du résumé: {str(e)}", exc_info=True)
        return (
            jsonify(
                {
                    "error": "Une erreur est survenue lors de la génération du résumé",
                    "details": str(e),
                }
            ),
            500,
        )


def extract_questions_from_text(text):
    """Tente d'extraire des questions à partir d'un texte brut"""
    import re

    # D'abord, essayer d'extraire le JSON depuis un bloc markdown
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if "questions" in data:
                logger.info(
                    f"JSON extrait du bloc markdown: {len(data['questions'])} questions"
                )
                return data["questions"]
        except json.JSONDecodeError as e:
            logger.warning(f"JSON dans bloc markdown invalide: {e}")

    # Essayer de trouver un objet JSON brut dans le texte
    json_match = re.search(r'\{[^{}]*"questions"[^{}]*\[.*?\]\s*\}', text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            if "questions" in data:
                logger.info(f"JSON brut extrait: {len(data['questions'])} questions")
                return data["questions"]
        except json.JSONDecodeError as e:
            logger.warning(f"JSON brut invalide: {e}")

    questions = []

    # Pattern pour détecter les questions suivies de réponses
    pattern = r"(?:^|\n)(\d+[\.\)]\s*)(.*?)(?=\n\d+[\.\)]|\n\n|$)"
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

    for num, question_text in matches:
        question_text = question_text.strip()
        if not question_text:
            continue

        # Essayer de séparer la question des réponses
        parts = re.split(r"\n+", question_text, 1)
        question = parts[0].strip()

        if len(parts) > 1:
            # Essayer d'extraire les options de réponse
            options = []
            answer = None
            explanation = None

            # Chercher des options de type A), B), etc.
            option_matches = re.findall(
                r"([A-Z]\))\s*(.*?)(?=\n[A-Z]\)|$)", parts[1], re.DOTALL
            )
            for opt_letter, opt_text in option_matches:
                opt_text = opt_text.strip()
                if opt_text:
                    options.append(opt_text)
                    # Si la réponse est marquée comme correcte
                    if (
                        "(correct)" in opt_text.lower()
                        or "(réponse)" in opt_text.lower()
                    ):
                        answer = opt_text.split("(")[0].strip()

            # Si on n'a pas trouvé d'options, utiliser le texte comme réponse courte
            if not options and parts[1].strip():
                answer = parts[1].strip()

            questions.append(
                {
                    "question_text": question,
                    "question_type": "qcm" if options else "reponse_courte",
                    "options": options,
                    "correct_answer": answer or "Réponse non spécifiée",
                    "explanation": explanation,
                }
            )

    return questions


@study_buddy_bp.route(
    "/documents/<int:document_id>/generate-quiz", methods=["POST", "GET"]
)
@login_required
def generate_quiz(document_id):
    """
    Génère un quiz à partir du document donné avec Gemini.

    Cette fonction est utilisée pour générer un quiz à partir d'un document en utilisant l'intégration
    Gemini. Elle vérifie d'abord si l'utilisateur est autorisé à générer un quiz à partir de ce document
    (c'est-à-dire s'il en est l'auteur). Ensuite, elle récupère le document spécifié à partir de la base
    de données et le rend à la vue de génération de quiz. Si la requête est GET, la fonction vérifie également
    si l'utilisateur a une progression de quiz enregistrée. Si aucune progression n'est trouvée, une nouvelle
    progression est créée pour l'utilisateur.

    Args:
        document_id (int): L'identifiant du document à partir duquel générer le quiz.

    Retourne :
        Si la requête est GET, renvoie une réponse HTML contenant un formulaire permettant à l'utilisateur
        de générer un quiz. Si la requête est POST, renvoie une réponse HTML contenant le quiz généré.
    """
    document = StudyDocument.query.get_or_404(document_id)

    if request.method == "GET":
        progress = StudyProgress.query.filter_by(user_id=current_user.id).first()
        if not progress:
            progress = StudyProgress(user_id=current_user.id)
            db.session.add(progress)
            db.session.commit()

        return render_template(
            "study_buddy/generate_quiz.html",
            document=document,
            title=f"Générer un quiz pour '{document.title}'",
            progress=progress,
        )

    # Vérifier que l'utilisateur est autorisé
    if document.user_id != current_user.id:
        return jsonify({"error": "Accès non autorisé"}), 403

    # Récupérer le contenu du document
    try:
        buffer = get_document_buffer(document)
    except Exception as e:
        return (
            jsonify({"error": f"Erreur lors de la récupération du document: {str(e)}"}),
            500,
        )

    if not buffer:
        return jsonify({"error": "Impossible de récupérer le contenu du document"}), 404

    content = extract_text_from_buffer(buffer, document.file_type)
    if not content:
        return jsonify({"error": "Impossible d'extraire le texte du document"}), 400

    try:
        # Récupérer les données JSON
        data = request.get_json()
        if not data:
            return jsonify({"error": "Aucune donnée fournie"}), 400

        # Récupérer les paramètres du quiz
        question_types = data.get("question_types", ["qcm", "vrai_faux"])
        difficulty = data.get("difficulty", "medium")
        num_questions = min(int(data.get("num_questions", 10)), 20)
        themes = data.get("themes", [])

        if not content or not content.strip():
            return (
                jsonify(
                    {"error": "Impossible de lire le fichier ou le document est vide"}
                ),
                400,
            )

        # Nettoyer le contenu pour éliminer les caractères non imprimables
        content = " ".join(content.split())

        if not content or not content.strip():
            return (
                jsonify(
                    {"error": "Impossible de lire le fichier ou le document est vide"}
                ),
                400,
            )

        # Nettoyer le contenu pour éliminer les caractères non imprimables
        content = " ".join(content.split())

        # Limiter la taille du contenu pour éviter les problèmes de token
        max_content_length = 10000  # Nombre de caractères max à envoyer à l'API
        if len(content) > max_content_length:
            content = content[:max_content_length] + "... [contenu tronqué]"

        # Créer un nouveau quiz
        quiz = Quiz(
            user_id=current_user.id,
            document_id=document_id,
            title=f"Quiz sur {document.title}",
            quiz_type=",".join(question_types),
            difficulty=difficulty,
        )
        db.session.add(quiz)
        db.session.flush()  # Pour obtenir l'ID du quiz

        # Générer les questions avec Gemini
        prompt = f"""
        IMPORTANT: Réponds UNIQUEMENT avec un objet JSON valide. 
        Ne commence PAS par du texte, salutations ou explications.
        Ne mets PAS le JSON dans un bloc markdown (pas de ```json).
        Retourne DIRECTEMENT l'objet JSON brut.

        Génère un quiz basé sur le contenu suivant:
        - Types de questions: {', '.join(question_types)}
        - Difficulté: {difficulty}
        - Nombre de questions: {num_questions}
        - Thèmes: {', '.join(themes) if themes else 'Aucun thème spécifique'}

        Contenu du document:
        {content[:10000]}  # Limiter la taille pour éviter les tokens excessifs

        Format de sortie EXACT (UNIQUEMENT ce JSON):
        {{
            "questions": [
                {{
                    "question_text": "Texte de la question",
                    "question_type": "qcm|vrai_faux|reponse_courte",
                    "options": ["Option 1", "Option 2", ...],  # Uniquement pour QCM
                    "correct_answer": "Réponse correcte",
                    "explanation": "Explication de la réponse"
                }},
                ...
            ]
        }}
        
        RAPPEL: Commence ta réponse par {{ et termine par }}.
        """

        try:
            # Appeler l'API Gemini
            logger.info(
                f"Envoi de la requête à Gemini avec le prompt: {prompt[:200]}..."
            )
            response = gemini.generate_response(prompt, use_system_prompt=False)
            logger.info(f"Réponse brute de Gemini: {response}")

            if not response.get("success"):
                error_msg = response.get(
                    "error", "Erreur inconnue lors de la génération des questions"
                )
                logger.error(f"Erreur Gemini: {error_msg}")
                raise Exception(error_msg)

            # Essayer de parser la réponse
            try:
                # Vérifier si la réponse contient une clé 'response' (format Gemini)
                if isinstance(response, dict) and "response" in response:
                    try:
                        # Essayer de parser le contenu de 'response' comme du JSON
                        response_content = response["response"]
                        if isinstance(response_content, str):
                            questions_data = json.loads(response_content).get(
                                "questions", []
                            )
                        else:
                            questions_data = response_content.get("questions", [])
                    except (json.JSONDecodeError, AttributeError) as je:
                        logger.warning(
                            f"Erreur de parsing JSON dans la réponse: {str(je)}"
                        )
                        questions_data = extract_questions_from_text(
                            str(response_content)
                        )
                # Ancien format de réponse (pour rétrocompatibilité)
                elif isinstance(response.get("text"), dict):
                    questions_data = response["text"].get("questions", [])
                else:
                    # Essayer de parser directement le texte comme JSON
                    questions_data = json.loads(response.get("text", "{}")).get(
                        "questions", []
                    )

                logger.info(
                    f"Questions extraites: {len(questions_data) if questions_data else 0}"
                )

                # Si toujours pas de questions, essayer d'extraire du texte brut
                if not questions_data:
                    logger.warning(
                        "Aucune question trouvée dans le format attendu, tentative d'extraction manuelle"
                    )
                    text_to_parse = response.get("response") or response.get("text", "")
                    questions_data = extract_questions_from_text(str(text_to_parse))

            except Exception as e:
                logger.error(f"Erreur lors du traitement de la réponse: {str(e)}")
                # Dernier recours : essayer d'extraire du texte brut de toute la réponse
                questions_data = extract_questions_from_text(str(response))

            if not questions_data:
                raise Exception(
                    "Aucune question valide n'a pu être générée à partir du contenu"
                )

            # Créer les questions dans la base de données
            for i, q_data in enumerate(questions_data[:num_questions], 1):
                try:
                    question = Question(
                        quiz_id=quiz.id,
                        question_text=q_data.get("question_text", f"Question {i}"),
                        question_type=q_data.get("question_type", "qcm"),
                        options=json.dumps(q_data.get("options", [])),
                        correct_answer=str(q_data.get("correct_answer", "")),
                        explanation=str(q_data.get("explanation", "")),
                        difficulty=difficulty,
                        order=i,
                    )
                    db.session.add(question)
                    logger.info(
                        f"Question {i} ajoutée: {question.question_text[:50]}..."
                    )

                except Exception as qe:
                    logger.error(f"Erreur création question {i}: {str(qe)}")
                    continue

            if not Question.query.filter_by(quiz_id=quiz.id).first():
                raise Exception("Aucune question valide n'a pu être créée")

            db.session.commit()

            return (
                jsonify(
                    {
                        "message": f"Quiz généré avec succès avec {Question.query.filter_by(quiz_id=quiz.id).count()} questions",
                        "quiz_id": quiz.id,
                    }
                ),
                201,
            )

        except Exception as e:
            db.session.rollback()
            logger.error(
                f"Erreur lors de la génération des questions: {str(e)}", exc_info=True
            )
            return (
                jsonify(
                    {
                        "error": "Erreur lors de la génération des questions",
                        "details": str(e),
                    }
                ),
                500,
            )

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la génération du quiz: {str(e)}", exc_info=True)
        return (
            jsonify(
                {
                    "error": "Une erreur est survenue lors de la génération du quiz",
                    "details": str(e),
                }
            ),
            500,
        )


@study_buddy_bp.route("/quiz/<int:quiz_id>")
@login_required
def take_quiz(quiz_id):
    """
    Permet de passer un quiz.

    Cette fonction prend en paramètre un identifiant de quiz et renvoie la page
    de passage du quiz correspondant. Elle vérifie d'abord si le quiz existe et
    est accessible par l'utilisateur actuellement connecté. Si le quiz n'existe pas,
    elle renvoie une erreur 404. Sinon, elle renvoie la page de passage du quiz.

    Args:
        quiz_id (int): L'identifiant du quiz à passer.

    Retourne :
        Renvoie la page de passage du quiz correspondant au format HTML.

    Si le quiz n'existe pas ou si l'utilisateur n'est pas autorisé à le passer,
    elle renvoie une erreur 404.
    """
    quiz = Quiz.query.get_or_404(quiz_id)

    # Vérifier que l'utilisateur est autorisé
    if quiz.user_id != current_user.id:
        flash("Accès non autorisé", "error")
        return redirect(url_for("study_buddy.index"))

    # Vérifier s'il y a une tentative en cours
    active_attempt = QuizAttempt.query.filter_by(
        user_id=current_user.id, quiz_id=quiz_id, is_completed=False
    ).first()

    if not active_attempt:
        # Créer une nouvelle tentative
        active_attempt = QuizAttempt(user_id=current_user.id, quiz_id=quiz_id)
        db.session.add(active_attempt)
        db.session.commit()

    # Récupérer les questions non répondues
    answered_question_ids = [a.question_id for a in active_attempt.answers]
    next_question = Question.query.filter(
        Question.quiz_id == quiz_id, ~Question.id.in_(answered_question_ids)
    ).first()

    # Si toutes les questions ont été répondues, terminer le quiz
    if not next_question and active_attempt.answers:
        active_attempt.complete_attempt()
        return redirect(
            url_for("study_buddy.quiz_results", attempt_id=active_attempt.id)
        )

    # Vérifier s'il y a des questions
    total_questions = Question.query.filter_by(quiz_id=quiz_id).count()
    if total_questions == 0:
        flash("Ce quiz ne contient aucune question.", "error")
        return redirect(
            url_for("study_buddy.document_detail", document_id=quiz.document_id)
        )

    # Récupérer ou créer la progression de l'utilisateur
    progress = StudyProgress.query.filter_by(user_id=current_user.id).first()
    if not progress:
        progress = StudyProgress(user_id=current_user.id)
        db.session.add(progress)
        db.session.commit()

    # Préparer les données pour le template
    context = {
        "quiz": quiz,
        "attempt": active_attempt,
        "question_actuelle": next_question,
        "question_number": len(answered_question_ids) + 1,
        "total_questions": total_questions,
        "progress": progress,
        "show_explanation": False,
        "attempt_id": active_attempt.id,
    }

    # Vérifier que toutes les variables nécessaires sont présentes
    required_vars = [
        "quiz",
        "attempt",
        "question_actuelle",
        "question_number",
        "total_questions",
        "progress",
        "show_explanation",
        "attempt_id",
    ]

    for var in required_vars:
        if var not in context:
            logging.error(f"Variable manquante dans le contexte: {var}")
            flash("Une erreur est survenue lors du chargement du quiz.", "error")
            return redirect(
                url_for("study_buddy.document_detail", document_id=quiz.document_id)
            )

    return render_template("study_buddy/quiz.html", **context)


@study_buddy_bp.route("/quiz/attempt/<int:attempt_id>/submit", methods=["POST"])
@login_required
def submit_quiz_answer(attempt_id):
    """
    Soumet une réponse à une question de quiz.

    Cette fonction est utilisée pour soumettre une réponse à une question de quiz. Elle vérifie d'abord
    si la requête contient du JSON et renvoie une erreur si ce n'est pas le cas. Ensuite, elle récupère les
    données JSON de la requête et vérifie si les données nécessaires sont présentes. Si les données sont incompletes,
    elle renvoie une réponse contenant une erreur.

    Args:
        attempt_id (int): L'identifiant de l'essai de quiz.

    Returns:
        Réponse JSON contenant le résultat de la soumission de la réponse ou une erreur si la requête n'est
        pas au format JSON ou si les données nécessaires sont manquantes.
    """
    if not request.is_json:
        return jsonify({"error": "Le contenu doit être au format JSON"}), 415

    # Récupérer les données JSON
    data = request.get_json()

    # Vérifier que les données nécessaires sont présentes
    if not data or "question_id" not in data or "answer" not in data:
        return jsonify({"error": "Données manquantes"}), 400

    # Récupérer la tentative de quiz
    attempt = QuizAttempt.query.get_or_404(attempt_id)

    # Vérifier que l'utilisateur est autorisé
    if attempt.user_id != current_user.id:
        return jsonify({"error": "Accès non autorisé"}), 403

    # Vérifier que la tentative n'est pas terminée
    if attempt.is_completed:
        return jsonify({"error": "Cette tentative est déjà terminée"}), 400

    # Récupérer la question et la réponse
    question_id = data.get("question_id")
    answer_data = data.get("answer")

    question = Question.query.get_or_404(question_id)

    # Vérifier que la question appartient au quiz de la tentative
    if question.quiz_id != attempt.quiz_id:
        return jsonify({"error": "Question invalide pour ce quiz"}), 400

    # Vérifier si la question a déjà été répondue dans cette tentative
    existing_answer = QuizAnswer.query.filter_by(
        quiz_attempt_id=attempt_id, question_id=question_id
    ).first()

    if existing_answer:
        return jsonify({"error": "Cette question a déjà été répondue"}), 400

    # Évaluer la réponse
    is_correct = False
    if question.question_type == "multiple_choice":
        # Pour les QCM, vérifier si la réponse correspond à la bonne option
        options = (
            json.loads(question.options)
            if isinstance(question.options, str)
            else question.options
        )
        correct_answers = [
            i for i, opt in enumerate(options) if opt.get("is_correct", False)
        ]
        is_correct = str(answer_data).strip().lower() in [
            str(ca).lower() for ca in correct_answers
        ]
    elif question.question_type == "true_false":
        # Pour Vrai/Faux, comparer la réponse
        correct_answer = (
            str(question.correct_answer).lower() if question.correct_answer else ""
        )
        is_correct = str(answer_data).lower() == correct_answer
    else:
        # Pour les réponses libres, comparer directement avec la réponse correcte
        correct_answer = (
            str(question.correct_answer).strip().lower()
            if question.correct_answer
            else ""
        )
        is_correct = str(answer_data).strip().lower() == correct_answer

    # Créer une nouvelle réponse
    try:
        answer = QuizAnswer(
            quiz_attempt_id=attempt_id,
            question_id=question_id,
            user_id=current_user.id,
            answer_data=(
                json.dumps(answer_data)
                if not isinstance(answer_data, str)
                else answer_data
            ),
            is_correct=is_correct,
            answered_at=datetime.utcnow(),
        )
        db.session.add(answer)

        # Mettre à jour le score de la tentative
        attempt.score = QuizAnswer.query.filter(
            QuizAnswer.quiz_attempt_id == attempt_id, QuizAnswer.is_correct
        ).count()
        attempt.updated_at = datetime.utcnow()

        # Vérifier si c'était la dernière question
        total_questions = len(attempt.quiz.questions)
        answered_questions = QuizAnswer.query.filter_by(
            quiz_attempt_id=attempt_id
        ).count()
        is_last_question = answered_questions >= total_questions

        if is_last_question:
            attempt.is_completed = True
            attempt.completed_at = datetime.utcnow()

        db.session.commit()

        # Préparer la réponse
        response_data = {
            "success": True,
            "message": "Réponse enregistrée avec succès",
            "is_correct": is_correct,
            "explanation": (
                question.explanation if hasattr(question, "explanation") else None
            ),
            "is_completed": is_last_question,
            "score": attempt.score,
            "total_questions": total_questions,
            "redirect": (
                url_for("study_buddy.quiz_results", attempt_id=attempt_id)
                if is_last_question
                else None
            ),
        }

        # Ajouter l'URL de redirection si nécessaire
        if is_last_question:
            response_data["redirect"] = url_for(
                "study_buddy.quiz_results", attempt_id=attempt_id
            )
        else:
            # URL pour la question suivante
            next_question_number = int(request.args.get("question_number", 1)) + 1
            response_data["next_url"] = url_for(
                "study_buddy.take_quiz",
                quiz_id=attempt.quiz_id,
                question_number=next_question_number,
            )

        return jsonify(response_data)

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Erreur lors de l'enregistrement de la réponse: {str(e)}"
        )
        return jsonify({"error": f"Erreur serveur: {str(e)}"}), 500


@study_buddy_bp.route("/quiz/attempt/<int:attempt_id>/results")
@login_required
def quiz_results(attempt_id):
    """
    Affiche les résultats d'une tentative de quiz.

    Cette fonction prend en paramètre un identifiant de tentative de quiz et renvoie la page
    de résultats correspondante. Elle vérifie d'abord si la tentative de quiz existe et est
    accessible par l'utilisateur actuellement connecté. Si la tentative de quiz n'existe pas,
    elle renvoie une erreur 404. Sinon, elle renvoie la page de résultats de la tentative de quiz.

    Args:
        attempt_id (int): L'identifiant de la tentative de quiz à afficher.

    Retourne :
        Renvoie la page de résultats de la tentative de quiz correspondante au format HTML.

    Si la tentative de quiz n'existe pas, elle renvoie une erreur 404.
    """
    attempt = QuizAttempt.query.get_or_404(attempt_id)

    # Vérifier que l'utilisateur est autorisé
    if attempt.user_id != current_user.id:
        flash("Accès non autorisé", "error")
        return redirect(url_for("study_buddy.index"))

    # S'assurer que la tentative est terminée
    if not attempt.is_completed:
        attempt.complete_attempt()
        db.session.commit()

    # Récupérer les réponses avec les questions
    answers = (
        QuizAnswer.query.filter_by(quiz_attempt_id=attempt_id)
        .join(Question, QuizAnswer.question_id == Question.id)
        .order_by(Question.order, Question.id)
        .all()
    )

    # Calculer le score
    total_questions = len(answers)
    correct_answers = sum(1 for a in answers if a.is_correct)
    score = (
        round((correct_answers / total_questions) * 100) if total_questions > 0 else 0
    )

    # Mettre à jour la progression de l'utilisateur
    progress = StudyProgress.get_or_create(user_id=current_user.id)
    progress.update_quiz_results(correct_answers, total_questions)
    db.session.commit()

    return render_template(
        "study_buddy/quiz_results.html",
        attempt=attempt,
        answers=answers,
        total_questions=total_questions,
        correct_answers=correct_answers,
        score=score,
        progress=progress,
    )


@study_buddy_bp.route("/quiz/attempt/<int:attempt_id>/restart", methods=["POST"])
@login_required
def restart_quiz(attempt_id):
    """
    Réinitialise et redémarre un quiz.

    Cette fonction prend en paramètre un identifiant de tentative de quiz et réinitialise
    le quiz en supprimant toutes les réponses existantes et en réinitialisant les statistiques
    liées à la tentative. Elle renvoie ensuite le client à la page de passage du quiz.

    Args:
        attempt_id (int): L'identifiant de la tentative de quiz à réinitialiser.

    Retourne :
        Renvoie le client à la page de passage du quiz correspondant au format HTML.

    Si la tentative de quiz n'existe pas ou si l'utilisateur n'est pas autorisé à la réinitialiser,
    elle renvoie une erreur 404.
    """
    attempt = QuizAttempt.query.get_or_404(attempt_id)

    # Vérifier que l'utilisateur est autorisé
    if attempt.user_id != current_user.id:
        flash("Accès non autorisé", "error")
        return redirect(url_for("study_buddy.index"))

    # Supprimer toutes les réponses existantes
    QuizAnswer.query.filter_by(quiz_attempt_id=attempt_id).delete()

    # Réinitialiser la tentative
    attempt.score = 0
    attempt.is_completed = False
    attempt.completed_at = None
    attempt.started_at = datetime.utcnow()

    db.session.commit()

    # Rediriger vers la première question
    return redirect(
        url_for("study_buddy.take_quiz", quiz_id=attempt.quiz_id, question_number=1)
    )


# API Endpoints pour les flashcards
@study_buddy_bp.route("/api/flashcards", methods=["GET"])
@login_required
def get_flashcards():
    """
    Récupère toutes les cartes de l'utilisateur connecté.

    Cette fonction est utilisée pour récupérer toutes les cartes de l'utilisateur connecté
    en tant que client. Elle vérifie d'abord si l'utilisateur est connecté et renvoie une
    erreur 401 si ce n'est pas le cas. Ensuite, elle récupère toutes les cartes de l'utilisateur
    connecté et les renvoie au client sous forme de JSON.

    Retourne :
        Renvoie toutes les cartes de l'utilisateur connecté au format JSON.

    Si l'utilisateur n'est pas connecté, elle renvoie une erreur 401.
    """
    try:
        # Récupérer les cartes de l'utilisateur
        flashcards = Flashcard.query.filter_by(user_id=current_user.id).all()

        # Préparer la réponse
        return (
            jsonify(
                {
                    "success": True,
                    "data": [
                        {
                            "id": card.id,
                            "front": card.front,
                            "back": card.back,
                            "deck_id": card.deck_id,
                            "created_at": (
                                card.created_at.isoformat() if card.created_at else None
                            ),
                            "updated_at": (
                                card.updated_at.isoformat() if card.updated_at else None
                            ),
                        }
                        for card in flashcards
                    ],
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Erreur lors de la récupération des cartes: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@study_buddy_bp.route("/api/flashcards/<int:card_id>", methods=["GET"])
@login_required
def get_flashcard(card_id):
    """
    Récupère une carte spécifique.

    Cette fonction prend en paramètre un identifiant de carte et renvoie les détails de
    cette carte au format JSON. Elle vérifie d'abord si l'utilisateur est connecté et renvoie une
    erreur 401 si ce n'est pas le cas. Ensuite, elle vérifie si la carte existe pour l'utilisateur
    connecté et renvoie une erreur 404 si elle n'existe pas. Enfin, elle renvoie les détails de la carte
    au format JSON.

    Args:
        card_id (int): L'identifiant de la carte à récupérer.

    Retourne :
        Renvoie les détails de la carte au format JSON.

    Si l'utilisateur n'est pas connecté, elle renvoie une erreur 401.
    Si la carte n'existe pas pour l'utilisateur connecté, elle renvoie une erreur 404.
    """
    try:
        card = Flashcard.query.filter_by(
            id=card_id, user_id=current_user.id
        ).first_or_404()

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "id": card.id,
                        "front": card.front,
                        "back": card.back,
                        "deck_id": card.deck_id,
                        "created_at": (
                            card.created_at.isoformat() if card.created_at else None
                        ),
                        "updated_at": (
                            card.updated_at.isoformat() if card.updated_at else None
                        ),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(
            f"Erreur lors de la récupération de la carte: {str(e)}"
        )
        return jsonify({"success": False, "error": str(e)}), 404


@study_buddy_bp.route("/api/flashcards", methods=["POST"])
@login_required
def create_flashcard_api():
    """
    Créer une nouvelle carte.

    Cette fonction est utilisée pour créer une nouvelle carte mémoire dans le système de répétition
    de l'utilisateur connecté. Elle vérifie d'abord si l'utilisateur est connecté et renvoie une erreur
    401 si ce n'est pas le cas. Ensuite, elle vérifie si les données nécessaires pour créer la carte sont
    présentes dans la requête et renvoie une erreur 400 si les données sont incomplètes. Enfin, elle crée
    la carte et renvoie les détails de la carte au format JSON.

    Retourne :
        Renvoie les détails de la nouvelle carte au format JSON.

    Si l'utilisateur n'est pas connecté, elle renvoie une erreur 401.
    Si les données nécessaires pour créer la carte sont manquantes, elle renvoie une erreur 400.
    """
    try:
        data = request.get_json()

        # Validation des données
        if (
            not data
            or "front" not in data
            or "back" not in data
            or "deck_id" not in data
        ):
            return jsonify({"success": False, "error": "Données manquantes"}), 400

        # Création de la carte
        new_card = Flashcard(
            front=data["front"],
            back=data["back"],
            deck_id=data["deck_id"],
            user_id=current_user.id,
        )

        db.session.add(new_card)
        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Carte créée avec succès",
                    "id": new_card.id,
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur lors de la création de la carte: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@study_buddy_bp.route("/api/flashcards/<int:card_id>", methods=["PUT"])
@login_required
def update_flashcard(card_id):
    """
    Mettre à jour une carte existante.

    Cette fonction permet de mettre à jour les informations d'une carte existante
    dans la base de données. La carte à mettre à jour est identifiée par son ID.
    Les informations à mettre à jour peuvent inclure le contenu de la face avant et
    de la face arrière de la carte.

    Paramètres:
        card_id (int): Identifiant unique de la carte à mettre à jour.

    Retourne:
        Si la mise à jour de la carte réussit, une réponse JSON contenant les informations suivantes :
            - success (bool): Indique si la requête a été effectuée avec succès
            - message (str): Message de confirmation de la mise à jour de la carte
            - id (int): Identifiant de la carte mise à jour
        Si la mise à jour de la carte échoue, une réponse JSON contenant les informations suivantes :
            - success (bool): Indique si la requête a été effectuée avec succès
            - error (str): Message d'erreur décrivant l'erreur survenue
            - code (int): Code HTTP associé à l'erreur
    """
    try:
        card = Flashcard.query.filter_by(
            id=card_id, user_id=current_user.id
        ).first_or_404()
        data = request.get_json()

        # Mise à jour des champs
        if "front" in data:
            card.front = data["front"]
        if "back" in data:
            card.back = data["back"]
        if "deck_id" in data:
            card.deck_id = data["deck_id"]

        card.updated_at = datetime.utcnow()
        db.session.commit()

        return (
            jsonify({"success": True, "message": "Carte mise à jour avec succès"}),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur lors de la mise à jour de la carte: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@study_buddy_bp.route("/api/flashcards/<int:card_id>", methods=["DELETE"])
@login_required
def delete_flashcard(card_id):
    """
    Supprime une carte.

    Cette fonction permet de supprimer une carte existante de la base de données.
    La carte à supprimer est identifiée par son ID. Cette requête est accessible
    uniquement à l'utilisateur propriétaire de la carte.

    Paramètres:
        card_id (int): Identifiant unique de la carte à supprimer.

    Retourne:
        Si la suppression de la carte réussit, une réponse JSON contenant les informations suivantes :
            - success (bool): Indique si la requête a été effectuée avec succès
            - message (str): Message de confirmation de la suppression de la carte
        Si la suppression de la carte échoue, une réponse JSON contenant les informations suivantes :
            - success (bool): Indique si la requête a été effectuée avec succès
            - error (str): Message d'erreur décrivant l'erreur survenue
            - code (int): Code HTTP associé à l'erreur
    """
    try:
        card = Flashcard.query.filter_by(
            id=card_id, user_id=current_user.id
        ).first_or_404()

        db.session.delete(card)
        db.session.commit()

        return jsonify({"success": True, "message": "Carte supprimée avec succès"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur lors de la suppression de la carte: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@study_buddy_bp.route("/flashcards")
@login_required
def flashcard_deck():
    """
    Afficher le jeu de cartes mémoire à réviser.

    Cette fonction est responsable de récupérer la progression de l'utilisateur
    et de l'afficher sur la page de révision de cartes mémoire.

    Retourne :
        Renvoie la page de révision de cartes mémoires avec la progression de l'utilisateur.
    """
    progress = StudyProgress.get_or_create(current_user.id)

    # Récupérer les cartes à réviser (celles qui sont dues)
    due_flashcards = Flashcard.get_due_cards(current_user.id)

    # Si aucune carte n'est due, proposer d'en créer de nouvelles ou d'en réviser d'anciennes
    if not due_flashcards:
        # Récupérer des cartes récentes
        due_flashcards = (
            Flashcard.query.filter_by(user_id=current_user.id)
            .order_by(Flashcard.updated_at.desc())
            .limit(5)
            .all()
        )

    return render_template(
        "study_buddy/flashcards.html",
        flashcards=due_flashcards,
        progress=progress,  # Ajout de la progression
    )


@study_buddy_bp.route("/flashcards/<int:flashcard_id>/review", methods=["POST"])
@login_required
def review_flashcard(flashcard_id):
    """
    Soumettre une révision de carte mémoire.

    Cette fonction est utilisée pour soumettre une révision de carte mémoire. Elle
    accepte une requête POST contenant la qualité de la révision (0-5) de la carte.
    La fonction vérifie que l'utilisateur est autorisé à réviser la carte et que la
    qualité de la révision est valide. Enfin, elle utilise la qualité de la révision
    pour mettre à jour l'état de la carte dans le système de répétition espacée.

    Paramètres:
        flashcard_id (int): Identifiant de la carte mémoire à réviser.

    Retourne :
        Si la révision de la carte réussit, une réponse JSON contenant les informations suivantes :
            - success (bool): Indique si la requête a été effectuée avec succès
            - message (str): Message de confirmation de la révision de la carte
        Si la révision de la carte échoue, une réponse JSON contenant les informations suivantes :
            - success (bool): Indique si la requête a été effectuée avec succès
            - error (str): Message d'erreur décrivant l'erreur survenue
            - code (int): Code HTTP associé à l'erreur
    """
    flashcard = Flashcard.query.get_or_404(flashcard_id)

    # Vérifier que l'utilisateur est autorisé
    if flashcard.user_id != current_user.id:
        return jsonify({"error": "Accès non autorisé"}), 403

    # Récupérer la qualité de la révision (0-5)
    quality = request.json.get("quality")
    if quality is None or not (0 <= int(quality) <= 5):
        return jsonify({"error": "Qualité de révision invalide"}), 400

    # Traiter la révision
    flashcard.process_review(int(quality))

    # Mettre à jour la progression
    progress = StudyProgress.query.filter_by(user_id=current_user.id).first()
    if progress:
        progress.update_study_time(30)  # 30 secondes par carte mémoire

    return jsonify(
        {
            "success": True,
            "next_review": (
                flashcard.due_date.isoformat() if flashcard.due_date else None
            ),
            "interval": flashcard.interval,
        }
    )


@study_buddy_bp.route("/flashcards/create", methods=["GET", "POST"])
@login_required
def create_flashcard():
    """
    Créer une nouvelle carte mémoire.

    Cette fonction est utilisée lorsqu'un utilisateur souhaite créer une nouvelle carte mémoire.
    Lorsqu'une requête POST est envoyée, la fonction vérifie les données du formulaire et les utilise pour créer une nouvelle
    carte mémoire. Si les données du formulaire sont invalides, une erreur est affichée et l'utilisateur est redirigé vers la page
    de création de carte mémoire. En cas de succès, l'utilisateur est redirigé vers la page de révision de cartes mémoires.

    Répond :
        Si la création de la carte réussit, un message de succès est affiché.
        Si la création de la carte échoue, un message d'erreur est affiché.

    Retourne :
        Si la requête est GET, renvoie une réponse HTML contenant un formulaire pour créer une carte mémoire.
        Si la requête est POST, redirige l'utilisateur vers la page de révision de cartes mémoires.
    """
    if request.method == "POST":
        front_text = request.form.get("front_text")
        back_text = request.form.get("back_text")
        document_id = request.form.get("document_id")
        tags = request.form.get("tags", "")

        if not front_text or not back_text:
            flash("Le texte de la carte ne peut pas être vide", "error")
            return redirect(request.url)

        # Créer la carte mémoire
        flashcard = Flashcard(
            user_id=current_user.id,
            document_id=document_id if document_id and document_id != "none" else None,
            front_text=front_text,
            back_text=back_text,
            tags=tags,
            status=FlashcardStatus.NEW.value,
            ease_factor=2.5,
            interval=0,
            due_date=datetime.utcnow(),
        )

        db.session.add(flashcard)

        # Mettre à jour les statistiques
        progress = StudyProgress.query.filter_by(user_id=current_user.id).first()
        if progress:
            progress.total_flashcards += 1

        db.session.commit()

        flash("Carte mémoire créée avec succès !", "success")

        if document_id and document_id != "none":
            return redirect(
                url_for("study_buddy.document_detail", document_id=document_id)
            )
        return redirect(url_for("study_buddy.flashcard_deck"))

    # GET: Afficher le formulaire de création
    document_id = request.args.get("document_id")
    progress = StudyProgress.get_or_create(current_user.id)
    return render_template(
        "study_buddy/create_flashcard.html", document_id=document_id, progress=progress
    )


@study_buddy_bp.route("/progress")
@login_required
def progress_tracking():
    """
    Afficher le suivi de la progression de l'utilisateur.

    Cette fonction est utilisée pour afficher les informations de suivi de la progression
    de l'utilisateur, telles que le nombre de quiz complétés, le nombre total de questions
    répondues, le nombre total de minutes passées en étude, et le taux de réussite des
    quiz réussis. Elle récupère également les dernières sessions d'étude de l'utilisateur pour
    les afficher dans un graphique.

    Retourne :
        Une réponse HTML contenant un tableau affichant les informations de suivi de la progression
        de l'utilisateur et un graphique des dernières sessions d'étude.
    """
    progress = StudyProgress.get_or_create(current_user.id)

    # Récupérer les tentatives de quiz complétées
    completed_quizzes = QuizAttempt.query.filter_by(
        user_id=current_user.id, is_completed=True
    ).all()

    # Calculer les statistiques
    stats = {
        "quizzes_completed": len(completed_quizzes),
        "total_questions_answered": progress.total_questions_answered,
        "total_study_time_minutes": (
            progress.total_study_time_seconds // 60
            if progress.total_study_time_seconds
            else 0
        ),
        "success_rate": (
            round(
                (
                    progress.total_correct_answers
                    / progress.total_questions_answered
                    * 100
                ),
                1,
            )
            if progress.total_questions_answered > 0
            else 0
        ),
    }

    # Récupérer les sessions d'étude des 30 derniers jours
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_sessions = (
        StudySession.query.filter(
            StudySession.user_id == current_user.id,
            StudySession.start_time >= thirty_days_ago,
        )
        .order_by(StudySession.start_time)
        .all()
    )

    # Préparer les données pour le graphique
    study_data = {}
    for session in recent_sessions:
        date_str = session.start_time.strftime("%Y-%m-%d")
        if date_str not in study_data:
            study_data[date_str] = 0
        study_data[date_str] += (
            session.duration_seconds if session.duration_seconds else 0
        )

    # Convertir en format pour Chart.js
    chart_labels = list(study_data.keys())
    chart_data = [
        seconds / 60 for seconds in study_data.values()
    ]  # Convertir en minutes

    # Récupérer les sujets les plus étudiés
    subjects = progress.subjects_progress if progress.subjects_progress else {}

    # Récupérer les quiz récents avec leurs détails
    recent_quizzes = []
    for attempt in completed_quizzes[:5]:  # Limiter aux 5 derniers
        quiz = attempt.quiz
        if quiz:
            # Calculer le score
            total_questions = Question.query.filter_by(quiz_id=quiz.id).count()
            correct_answers = QuizAnswer.query.filter_by(
                attempt_id=attempt.id, is_correct=True
            ).count()
            score = (
                round((correct_answers / total_questions * 100), 1)
                if total_questions > 0
                else 0
            )

            # Calculer le temps passé (placeholder)
            time_spent = 0
            if attempt.completed_at and attempt.started_at:
                time_diff = attempt.completed_at - attempt.started_at
                time_spent = int(time_diff.total_seconds() / 60)  # en minutes

            recent_quizzes.append(
                {
                    "name": quiz.title,
                    "topic": quiz.quiz_type if quiz.quiz_type else "Quiz",
                    "score": score,
                    "completed_at": attempt.completed_at,
                    "time_spent": time_spent if time_spent > 0 else 5,  # Minimum 5 min
                }
            )

    # Placeholder pour les objectifs (à implémenter plus tard)
    goals = []

    return render_template(
        "study_buddy/progress.html",
        progress=progress,
        chart_labels=json.dumps(chart_labels),
        chart_data=json.dumps(chart_data),
        subjects=subjects,
        stats=stats,  # Ajout des statistiques
        recent_quizzes=recent_quizzes,  # Ajout des quiz récents
        goals=goals,  # Ajout des objectifs
    )


# Fonction pour enregistrer le blueprint dans l'application
def init_app(app):
    # Créer le dossier de téléchargement s'il n'existe pas
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Enregistrer le blueprint
    app.register_blueprint(study_buddy_bp)

    # Ajouter le contexte pour les templates
    @app.context_processor
    def inject_study_buddy_vars():
        context = {"now": datetime.utcnow(), "study_buddy_nav": True}
        if hasattr(current_user, "is_authenticated") and current_user.is_authenticated:
            from models.study_progress import StudyProgress

            progress = StudyProgress.get_or_create(current_user.id)
            context["progress"] = progress
        return context


@study_buddy_bp.route("/documents/<int:document_id>/delete", methods=["POST"])
@login_required
def delete_document(document_id):
    """
    Supprimer un document.
    """
    document = StudyDocument.query.get_or_404(document_id)
    if document.user_id != current_user.id:
        flash("Accès non autorisé", "error")
        return redirect(url_for("study_buddy.index"))

    # Supprimer fichier local si existe
    if not document.file_path.startswith(("http://", "https://")) and os.path.exists(
        document.file_path
    ):
        try:
            os.remove(document.file_path)
        except Exception as e:
            current_app.logger.error(f"Erreur suppression fichier local: {e}")

    db.session.delete(document)
    db.session.commit()
    flash("Document supprimé avec succès.", "success")
    return redirect(url_for("study_buddy.index"))


@study_buddy_bp.route("/documents/<int:document_id>/edit", methods=["POST"])
@login_required
def edit_document(document_id):
    """
    Modifier les métadonnées d'un document.
    """
    document = StudyDocument.query.get_or_404(document_id)
    if document.user_id != current_user.id:
        return jsonify({"success": False, "error": "Accès non autorisé"}), 403

    title = request.form.get("title")
    description = request.form.get("description")

    if title:
        document.title = title

    if description is not None:
        # Met à jour la description dans content_metadata
        metadata = document.content_metadata or {}
        metadata["description"] = description
        document.content_metadata = metadata

    db.session.commit()
    return jsonify({"success": True})
