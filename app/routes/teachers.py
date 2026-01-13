from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    current_app,
)
from flask_login import login_required, current_user
from datetime import datetime
import json
from datetime import date, timedelta

from app.extensions import db
from app.models.user import User
from app.models.enseignant import Enseignant
from app.models.etudiant import Etudiant
from app.models.matiere import Matiere
from app.models.emploi_temps import EmploiTemps
from app.models.filiere import Filiere
from app.models.devoir import Devoir
from app.models.devoir_vu import DevoirVu
from app.models.notification import Notification
from app.services.notification_service import NotificationService
from app.models.presence import Presence
from app.models.note import Note
from app.models.note_modification_request import NoteModificationRequest
from app.services.validation_service import ValidationService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


teachers_bp = Blueprint("teachers", __name__, url_prefix="/enseignant")


@teachers_bp.route("/dashboard")
@login_required
def dashboard():
    """
    Route pour afficher le tableau de bord de l'enseignant.
    """
    if current_user.role != "enseignant":
        flash("Accès non autorisé.", "error")
        return redirect(url_for("main.index"))

    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()
    if not enseignant:
        flash("Profil enseignant non trouvé.", "error")
        return redirect(url_for("main.index"))

    # Matières enseignées
    matieres = Matiere.query.filter_by(enseignant_id=enseignant.id).all()

    # Étudiants (tous ceux des filières/années enseignées)
    filieres = []
    annees = []
    if enseignant.filieres_enseignees:
        try:
            data = json.loads(enseignant.filieres_enseignees)
            filieres = data.get("filieres", [])
            annees = data.get("annees", [])
        except Exception:
            pass

    etudiants_count = 0
    if filieres and annees:
        etudiants_count = Etudiant.query.filter(
            Etudiant.filiere.in_(filieres), Etudiant.annee.in_(annees)
        ).count()

    # Cours aujourd'hui (emploi du temps)

    # Mapper le jour anglais vers le libellé français utilisé dans EmploiTemps
    day_map = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche",
    }
    today_en = datetime.now().strftime("%A")
    today = day_map.get(today_en, today_en)

    # On récupère tous les emplois du temps du jour pour cet enseignant
    cours_aujourdhui = (
        EmploiTemps.query.join(Matiere, EmploiTemps.matiere_id == Matiere.id)
        .join(Enseignant, Matiere.enseignant_id == Enseignant.id)
        .join(User, Enseignant.user_id == User.id)
        .join(Filiere, EmploiTemps.filiere_id == Filiere.id)
        .filter(EmploiTemps.jour == today, User.nom == enseignant.user.nom)
        .order_by(EmploiTemps.heure_debut)
        .all()
    )
    cours_aujourdhui_count = len(cours_aujourdhui)

    # Devoirs à corriger (devoirs de l'enseignant avec fichier uploadé par les étudiants)
    devoirs_a_corriger = (
        Devoir.query.filter_by(enseignant_id=enseignant.id)
        .filter(Devoir.fichier is not None)
        .count()
    )

    # Notifications récentes
    notifications = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.date_created.desc())
        .limit(5)
        .all()
    )

    # Prendre la première matière si elle existe
    matiere_courante = matieres[0] if matieres else None

    if request.is_json or request.args.get("format") == "json":
        # Support Mobile : Retourner les stats dashboard enseignant
        return jsonify(
            {
                "success": True,
                "data": {
                    "subjects_count": len(matieres),
                    "students_count": etudiants_count,
                    "courses_today_count": cours_aujourdhui_count,
                    "assignments_count": devoirs_a_corriger,
                    "notifications_count": len(notifications),
                    "courses_today": [
                        {
                            "heure_debut": c.heure_debut.strftime("%H:%M"),
                            "heure_fin": c.heure_fin.strftime("%H:%M"),
                            "salle": c.salle.nom_salle if c.salle else "Non définie",
                            "matiere": c.matiere.nom_matiere if c.matiere else "-",
                        }
                        for c in cours_aujourdhui
                    ],
                },
            }
        )

    return render_template(
        "enseignant/dashboard.html",
        matieres=matieres,
        matiere=matiere_courante,  # Ajout de la matière courante
        enseignant=enseignant,
        etudiants_count=etudiants_count,
        cours_aujourdhui_count=cours_aujourdhui_count,
        devoirs_a_corriger=devoirs_a_corriger,
        cours_aujourdhui=cours_aujourdhui,
        notifications=notifications,
    )


@teachers_bp.route("/cours-aujourdhui")
@login_required
def cours_aujourdhui():
    """
    Fonction qui affiche la liste des cours de l'enseignant de l'utilisateur actuel
    qui ont lieu aujourd'hui.
    """

    if current_user.role != "enseignant":
        flash("Accès non autorisé.", "error")
        return redirect(url_for("main.index"))
    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()
    if not enseignant:
        flash("Profil enseignant non trouvé.", "error")
        return redirect(url_for("main.index"))

    day_map = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche",
    }
    today_en = datetime.now().strftime("%A")
    today = day_map.get(today_en, today_en)

    # Même logique que sur le dashboard : tous les cours du jour pour cet enseignant
    cours_aujourdhui = (
        EmploiTemps.query.join(Matiere, EmploiTemps.matiere_id == Matiere.id)
        .join(Enseignant, Matiere.enseignant_id == Enseignant.id)
        .join(User, Enseignant.user_id == User.id)
        .join(Filiere, EmploiTemps.filiere_id == Filiere.id)
        .filter(EmploiTemps.jour == today, User.nom == enseignant.user.nom)
        .order_by(EmploiTemps.heure_debut)
        .all()
    )
    if request.is_json or request.args.get("format") == "json":
        return jsonify(
            {
                "success": True,
                "data": [
                    {
                        "filiere_nom": c.filiere_nom,
                        "heure_debut": c.heure_debut.strftime("%H:%M"),
                        "heure_fin": c.heure_fin.strftime("%H:%M"),
                        "salle": c.salle_nom,
                        "matiere_nom": c.matiere_nom,
                    }
                    for c in cours_aujourdhui
                ],
            }
        )

    return render_template(
        "enseignant/cours_aujourdhui.html", cours_aujourdhui=cours_aujourdhui
    )


@teachers_bp.route("/notes", methods=["GET", "POST"])
@login_required
def notes():
    """
    Permet à l'enseignant de consulter les notes de ses étudiants.
    """

    if current_user.role != "enseignant":
        if request.args.get("format") == "json" or request.is_json:
            return jsonify({"success": False, "error": "Accès non autorisé"}), 403
        flash("Accès non autorisé.", "error")
        return redirect(url_for("main.index"))

    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()
    try:
        data = json.loads(enseignant.filieres_enseignees)
        filieres = data.get("filieres", [])
        annees = data.get("annees", [])
    except Exception:
        filieres = []
        annees = []

    selected_filiere = request.args.get("filiere")
    selected_annee = request.args.get("annee")
    if selected_filiere and selected_filiere not in filieres:
        selected_filiere = None
    if selected_annee and selected_annee not in annees:
        selected_annee = None

    etudiants_query = Etudiant.query.filter(
        Etudiant.filiere.in_(filieres), Etudiant.annee.in_(annees)
    )
    if selected_filiere:
        etudiants_query = etudiants_query.filter(Etudiant.filiere == selected_filiere)
    if selected_annee:
        etudiants_query = etudiants_query.filter(Etudiant.annee == selected_annee)
    etudiants = etudiants_query.all()

    matieres = Matiere.query.filter_by(enseignant_id=enseignant.id).all()

    # Récupérer les demandes de modification en attente pour cet enseignant
    pending_requests = NoteModificationRequest.query.filter_by(
        enseignant_id=enseignant.id, statut="pending"
    ).all()
    # Set des IDs de notes ayant une demande en attente
    pending_note_ids = {req.note_id for req in pending_requests}

    # Structure pour le frontend:
    # Key: "etudiant_id_matiere_id_type_eval" -> {valeur, note_id, has_pending}
    notes_existantes_js = {}
    dates_evaluations = {}

    for matiere in matieres:
        notes_matiere = Note.query.filter_by(matiere_id=matiere.id).all()
        for note in notes_matiere:
            key = f"{note.etudiant_id}_{matiere.id}_{note.type_evaluation}"

            # Vérifier si cette note a une modification en attente
            has_pending = note.id in pending_note_ids

            notes_existantes_js[key] = {
                "valeur": note.note,
                "note_id": note.id,
                "has_pending": has_pending,
            }

            # Récupérer la date d'évaluation si elle existe
            date_key = f"{matiere.id}_{note.type_evaluation}"
            if date_key not in dates_evaluations and note.date_evaluation:
                dates_evaluations[date_key] = note.date_evaluation.strftime("%Y-%m-%d")

    if request.method == "POST":
        if request.is_json:
            data = request.get_json()
            etudiant_id = data.get("etudiant_id")
            matiere_id = data.get("matiere_id")
            type_eval = data.get("type_eval")
            note_val = data.get("note")
        else:
            etudiant_id = request.form["etudiant_id"]
            matiere_id = request.form["matiere_id"]
            type_eval = request.form["type_eval"]
            note_val = request.form["note"]

        # --- RESTRICTION SAISIE ---
        # Vérifier si une période d'évaluation est ouverte pour ce type
        from app.models.evaluation_period import EvaluationPeriod
        from datetime import date

        type_upper = type_eval.upper()
        if type_upper == "TP":
            type_upper = "DEVOIR"

        today = date.today()
        active_period = EvaluationPeriod.query.filter(
            EvaluationPeriod.type_eval == type_upper,
            EvaluationPeriod.start_date <= today,
            EvaluationPeriod.end_date >= today,
        ).first()

        # Si pas de période active (Sauf si Admin/SuperUser ? Non, user demande restriction stricte)
        if not active_period:
            msg = f"La saisie des notes pour '{type_eval}' est fermée actuellement."
            if request.is_json:
                return jsonify({"success": False, "error": msg}), 403
            flash(msg, "error")
            return redirect(url_for("teachers.notes"))
        # --------------------------

        try:
            note_float = float(note_val)
        except (TypeError, ValueError):
            if request.is_json:
                return jsonify({"success": False, "error": "Note invalide"}), 400
            flash("Note invalide.", "error")
            return redirect(url_for("teachers.notes"))

        etu = Etudiant.query.get(etudiant_id)
        if not etu or etu.filiere not in filieres or etu.annee not in annees:
            msg = "Vous n'avez pas le droit de modifier cette note."
            if request.is_json:
                return jsonify({"success": False, "error": msg}), 403
            flash(msg, "error")
            return redirect(url_for("teachers.notes"))

        note = Note.query.filter_by(
            etudiant_id=etudiant_id, matiere_id=matiere_id, type_evaluation=type_eval
        ).first()
        if note:
            note.note = note_float
        else:
            note = Note(
                etudiant_id=etudiant_id,
                matiere_id=matiere_id,
                type_evaluation=type_eval,
                note=note_float,
            )
            db.session.add(note)
        db.session.commit()

        # Notification
        try:
            matiere = Matiere.query.get(matiere_id)
            NotificationService.notify_grade_recorded(
                etu, matiere, type_eval, note_float
            )
        except Exception as e:
            current_app.logger.error(f"Error in automatic notification: {e}")

        if request.is_json:
            return jsonify({"success": True, "message": "Note enregistrée"})
        flash("Note enregistrée.", "success")
        return redirect(url_for("teachers.notes"))

    if request.args.get("format") == "json" or request.is_json:
        return jsonify(
            {
                "success": True,
                "data": {
                    "etudiants": [
                        {
                            "id": e.id,
                            "nom": e.nom,
                            "prenom": e.prenom,
                            "filiere": e.filiere,
                            "annee": e.annee,
                            "gender": e.gender,
                        }
                        for e in etudiants
                    ],
                    "matieres": [
                        {
                            "id": m.id,
                            "nom": m.nom,
                            "filiere": m.filiere.nom if m.filiere else "",
                        }
                        for m in matieres
                    ],
                    "notes_existantes": notes_existantes_js,
                    "dates_evaluations": dates_evaluations,
                    "filieres": filieres,
                    "annees": annees,
                    "selected_filiere": selected_filiere,
                    "selected_annee": selected_annee,
                },
            }
        )

    return render_template(
        "enseignant/notes.html",
        etudiants=etudiants,
        matieres=matieres,
        notes_existantes=notes_existantes_js,
        dates_evaluations=dates_evaluations,
        filieres_enseignees=filieres,
        annees_enseignees=annees,
        selected_filiere=selected_filiere,
        selected_annee=selected_annee,
    )


@teachers_bp.route("/api/grades/get", methods=["GET"])
@login_required
def get_grades_json():
    """
    API pour récupérer les notes d'une matière et d'un type d'évaluation spécifiques.
    Retourne un JSON map: { etudiant_id: { valeur: float, note_id: int, has_pending: bool } }
    """
    if current_user.role != "enseignant":
        return jsonify({"success": False, "message": "Accès non autorisé"}), 403

    matiere_id = request.args.get("matiere_id")
    type_eval = request.args.get("type_eval")

    if not matiere_id or not type_eval:
        return jsonify({"success": False, "message": "Paramètres manquants"}), 400

    # Vérifier que l'enseignant enseigne cette matière
    matiere = Matiere.query.get_or_404(matiere_id)
    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()

    if matiere.enseignant_id != enseignant.id:
        return (
            jsonify(
                {"success": False, "message": "Accès non autorisé à cette matière"}
            ),
            403,
        )

    # Récupérer les notes
    notes = Note.query.filter_by(matiere_id=matiere.id, type_evaluation=type_eval).all()

    # Récupérer les modifications en attente
    pending_requests = NoteModificationRequest.query.filter_by(
        enseignant_id=enseignant.id, statut="pending"
    ).all()
    pending_note_ids = {req.note_id for req in pending_requests}

    grades_map = {}
    date_eval = None

    for note in notes:
        grades_map[note.etudiant_id] = {
            "valeur": note.note,
            "note_id": note.id,
            "has_pending": note.id in pending_note_ids,
        }
        if not date_eval and note.date_evaluation:
            date_eval = note.date_evaluation.strftime("%Y-%m-%d")

    return jsonify({"success": True, "grades": grades_map, "date_eval": date_eval})


@teachers_bp.route("/rattrapages", methods=["GET", "POST"])
@login_required
def manage_rattrapage():
    """
    Similaire à 'notes', mais affiche uniquement les étudiants
    ayant une moyenne < 10 dans les matières de l'enseignant.
    Permet de saisir la note de rattrapage.
    """
    if current_user.role != "enseignant":
        return redirect(url_for("main.index"))

    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()
    matieres = Matiere.query.filter_by(enseignant_id=enseignant.id).all()

    # Récupérer les étudiants concernés
    # On itère sur toutes les matières de l'enseignant
    # Pour chaque matière, on récupère les étudiants de la filière/année
    # On calcule leur moyenne via ValidationService
    # Si < 10, on les ajoute à la liste

    rattrapage_data = []  # [(Etudiant, Matiere, Moyenne, NoteRattrapageActual, NoteID)]

    # Optimisation: charger les étudiants une fois par filière/année si possible
    # Pour faire simple : boucle car ValidationService est granulaire

    # D'abord identifier les groupes (Filiere, Annee)
    try:
        data = json.loads(enseignant.filieres_enseignees)
        filieres_noms = data.get("filieres", [])
        annees_noms = data.get("annees", [])
    except Exception as e:
        filieres_noms = []
        annees_noms = []
        logger.error("Erreur :", e)

    # Charger tous les étudiants potentiels
    candidats = Etudiant.query.filter(
        Etudiant.filiere.in_(filieres_noms), Etudiant.annee.in_(annees_noms)
    ).all()

    # Pour chaque étudiant, vérifier chaque matière de l'enseignant
    # qui correspond à sa filière/année

    for etu in candidats:
        for mat in matieres:
            # Vérifier correspondance filière/année (si la matière est spécifique)
            # Matiere a filier_id.
            if mat.filiere.nom == etu.filiere and mat.annee == etu.annee:
                is_valid, moyenne, msg = ValidationService.valider_matiere(
                    etu.id, mat.id
                )
                if not is_valid:
                    # Il est en rattrapage
                    # Chercher note rattrapage existante
                    notes = ValidationService.get_notes(etu.id, mat.id)
                    note_rattrapage_obj = next(
                        (n for n in notes if n.type_evaluation == "Rattrapage"), None
                    )
                    valeur_r = note_rattrapage_obj.note if note_rattrapage_obj else None

                    rattrapage_data.append(
                        {
                            "etudiant": etu,
                            "matiere": mat,
                            "moyenne": moyenne,
                            "note_actuelle": valeur_r,
                            "user": User.query.get(etu.user_id),
                        }
                    )

    if request.is_json or request.args.get("format") == "json":
        if request.method == "POST":
            # Si c'était un JSON POST, on traite différemment ?
            # Non, plus simple de garder la logique et retourner success
            pass
        else:
            return jsonify(
                {
                    "success": True,
                    "data": [
                        {
                            "etudiant_id": item["etudiant"].id,
                            "matiere_id": item["matiere"].id,
                            "nom": item["user"].nom,
                            "prenom": item["user"].prenom,
                            "numero_etudiant": item["etudiant"].numero_etudiant,
                            "matiere_nom": item["matiere"].nom,
                            "filiere": item["matiere"].filiere.nom,
                            "annee": item["matiere"].annee,
                            "moyenne": item["moyenne"],
                            "note_actuelle": item["note_actuelle"],
                        }
                        for item in rattrapage_data
                    ],
                }
            )

    if request.method == "POST":
        if request.is_json:
            etu_id = request.json.get("etudiant_id")
            matiere_id = request.json.get("matiere_id")
            note_val = request.json.get("note")
        else:
            etu_id = request.form.get("etudiant_id")
            matiere_id = request.form.get("matiere_id")
            note_val_str = request.form.get("note")
            try:
                note_val = float(note_val_str) if note_val_str else None
            except ValueError:
                note_val = None

        if etu_id and matiere_id and note_val is not None:
            try:
                # Sauvegarder/Mettre à jour
                note_obj = Note.query.filter_by(
                    etudiant_id=etu_id,
                    matiere_id=matiere_id,
                    type_evaluation="Rattrapage",
                ).first()

                if note_obj:
                    note_obj.note = note_val
                else:
                    note_obj = Note(
                        etudiant_id=etu_id,
                        matiere_id=matiere_id,
                        type_evaluation="Rattrapage",
                        note=note_val,
                    )
                    db.session.add(note_obj)

                db.session.commit()
                if request.is_json or request.args.get("format") == "json":
                    return jsonify(
                        {"success": True, "message": "Note de rattrapage enregistrée"}
                    )
                flash("Note de rattrapage enregistrée", "success")
            except Exception as e:
                db.session.rollback()
                if request.is_json or request.args.get("format") == "json":
                    return jsonify({"success": False, "error": str(e)}), 500
                flash("Erreur lors de l'enregistrement", "error")
        else:
            if request.is_json or request.args.get("format") == "json":
                return jsonify({"success": False, "error": "Données invalides"}), 400
            flash("Note invalide", "error")

        return redirect(url_for("teachers.manage_rattrapage"))

    return render_template("enseignant/manage_rattrapage.html", liste=rattrapage_data)


@teachers_bp.route("/request-modification", methods=["POST"])
@login_required
def request_modification():
    """
    Crée une demande de modification de note.
    """
    if current_user.role != "enseignant":
        return jsonify({"success": False, "message": "Accès non autorisé"}), 403

    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()

    note_id = request.form.get("note_id")
    nouvelle_valeur = request.form.get("nouvelle_valeur")
    raison = request.form.get("raison")

    if not all([note_id, nouvelle_valeur, raison]):
        return jsonify({"success": False, "message": "Données manquantes"}), 400

    note = Note.query.get(note_id)
    if not note:
        return jsonify({"success": False, "message": "Note introuvable"}), 404

    # Vérifier que la note appartient à une matière de l'enseignant
    if note.matiere.enseignant_id != enseignant.id:
        return (
            jsonify(
                {"success": False, "message": "Vous ne pouvez pas modifier cette note"}
            ),
            403,
        )

    # Créer la demande
    demande = NoteModificationRequest(
        note_id=note.id,
        enseignant_id=enseignant.id,
        nouvelle_valeur=float(nouvelle_valeur),
        raison=raison,
        statut="pending",
    )
    db.session.add(demande)
    db.session.commit()

    # NOTIFICATIONS
    # 1. Aux Admins
    admins = User.query.filter_by(role="admin").all()
    for admin in admins:
        Notification.creer_notification(
            user_id=admin.id,
            titre="Demande de modification de note",
            message=f"L'enseignant {current_user.nom} souhaite modifier une note en {note.matiere.nom}. Raison: {raison}",
            type="info",
        )

    # 2. A l'enseignant (confirmation)
    Notification.creer_notification(
        user_id=current_user.id,
        titre="Demande envoyée",
        message=f"Votre demande de modification pour {note.etudiant.user.nom} a bien été transmise.",
        type="success",
    )
    db.session.commit()

    return jsonify({"success": True, "message": "Demande envoyée avec succès"})


@teachers_bp.route("/devoirs", methods=["GET", "POST"])
@login_required
def devoirs():
    """
    Permet à l'enseignant de consulter et de gérer les devoirs de ses étudiants.
    """
    if current_user.role != "enseignant":
        flash("Accès non autorisé.", "error")
        return redirect(url_for("main.index"))

    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()
    try:
        data = json.loads(enseignant.filieres_enseignees)
        filieres = data.get("filieres", [])
        annees = data.get("annees", [])
    except Exception:
        filieres = []
        annees = []

    if request.is_json or request.args.get("format") == "json":
        if request.method == "GET":
            return jsonify({"success": True, "filieres": filieres, "annees": annees})

    if request.method == "POST":
        if request.is_json:
            titre = request.json.get("titre")
            description = request.json.get("description")
            type_devoir = request.json.get("type")
            filiere = request.json.get("filiere")
            annee = request.json.get("annee")
            date_limite = request.json.get("date_limite")
            file_url = request.json.get("file_url")
        else:
            titre = request.form["titre"]
            description = request.form["description"]
            type_devoir = request.form["type"]
            filiere = request.form["filiere"]
            annee = request.form["annee"]
            date_limite = request.form.get("date_limite")
            file_url = request.form.get("file_url")

        # Création du devoir
        devoir = Devoir(
            titre=titre,
            description=description,
            type=type_devoir,
            filiere=filiere,
            annee=annee,
            enseignant_id=enseignant.id,
            date_limite=date_limite if date_limite else None,
            fichier=file_url,
        )
        db.session.add(devoir)
        db.session.commit()

        # Notifier tous les étudiants concernés
        etudiants = Etudiant.query.filter_by(filiere=filiere, annee=annee).all()
        for etu in etudiants:
            Notification.creer_notification(
                user_id=etu.user_id,
                titre=f"Nouveau {type_devoir}",
                message=f"Sujet : {titre} - {filiere} {annee}",
                type="info",
            )
        db.session.commit()

        if request.is_json or request.args.get("format") == "json":
            return jsonify(
                {"success": True, "message": f"{type_devoir.capitalize()} envoyé."}
            )

        flash(
            f"{type_devoir.capitalize()} envoyé à tous les étudiants de {filiere} {annee}.",
            "success",
        )
        return redirect(url_for("teachers.devoirs"))

    return render_template("enseignant/devoirs.html", filieres=filieres, annees=annees)


@teachers_bp.route("/emploi-temps")
@login_required
def emploi_temps():
    """Page d'accès à l'emploi du temps de l'enseignant.

    La page est remplie côté client via l'API JSON correspondante.
    """
    if current_user.role != "enseignant":
        flash("Accès non autorisé.", "error")
        return redirect(url_for("main.index"))

    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()
    if not enseignant:
        flash("Aucun profil enseignant trouvé.", "error")
        return redirect(url_for("teachers.dashboard"))

    return render_template("enseignant/emploi_temps.html")


@teachers_bp.route("/api/emploi-temps", methods=["GET"])
@login_required
def api_emploi_temps():
    """Récupère les emplois du temps de l'enseignant courant en JSON."""
    if current_user.role != "enseignant":
        flash("Accès non autorisé.", "error")
        return jsonify({"error": "Accès non autorisé"}), 403

    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()
    if not enseignant:
        flash("Profil enseignant introuvable.", "error")
        return jsonify({"error": "Profil enseignant introuvable"}), 404

    filieres = []
    annees = []
    try:
        data = json.loads(enseignant.filieres_enseignees)
        filieres = data.get("filieres", [])
        annees = data.get("annees", [])
    except Exception:
        pass

    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]

    # Définition des créneaux fixes (Cours et Pauses)
    horaire_config = [
        {"label": "07:00 - 10:00", "type": "cours"},
        {"label": "10:00 - 10:30", "type": "pause", "nom": "Récréation"},
        {"label": "10:30 - 12:30", "type": "cours"},
        {"label": "12:30 - 13:30", "type": "pause", "nom": "Déjeuner"},
        {"label": "13:30 - 15:30", "type": "cours"},
        {"label": "15:30 - 16:00", "type": "pause", "nom": "Pause"},
        {"label": "16:00 - 18:00", "type": "cours"},
    ]

    if not filieres or not annees:
        return jsonify(
            {
                "jours": jours,
                "horaires": [h["label"] for h in horaire_config],
                "horaire_config": horaire_config,
                "creneaux": [],
            }
        )

    filiere_ids = [
        Filiere.query.filter_by(nom=f).first().id
        for f in filieres
        if Filiere.query.filter_by(nom=f).first()
    ]

    emplois = (
        EmploiTemps.query.join(Matiere, EmploiTemps.matiere_id == Matiere.id)
        .filter(
            EmploiTemps.filiere_id.in_(filiere_ids),
            Matiere.enseignant_id == enseignant.id,
        )
        .all()
    )

    def format_label(emploi):
        hd = emploi.heure_debut
        hf = emploi.heure_fin
        if isinstance(hd, str):
            hd_h, hd_m = map(int, hd.split(":")[:2])
        else:
            hd_h, hd_m = hd.hour, hd.minute
        if isinstance(hf, str):
            hf_h, hf_m = map(int, hf.split(":")[:2])
        else:
            hf_h, hf_m = hf.hour, hf.minute
        return f"{hd_h:02d}:{hd_m:02d} - {hf_h:02d}:{hf_m:02d}"

    creneaux_json = []
    for e in emplois:
        if not e.heure_debut or not e.heure_fin:
            continue
        label = format_label(e)
        matiere = Matiere.query.get(e.matiere_id) if e.matiere_id else None

        creneaux_json.append(
            {
                "jour": e.jour,
                "horaire": label,
                "matiere": matiere.nom if matiere else None,
                "filiere": e.filiere.nom if e.filiere else "Inconnue",
                "annee": matiere.annee if matiere else "N/A",
                "salle": e.salle,
                "type": "cours",
            }
        )

    return jsonify(
        {
            "jours": jours,
            "horaires": [h["label"] for h in horaire_config],
            "horaire_config": horaire_config,
            "creneaux": creneaux_json,
        }
    )


@teachers_bp.route("/presence", methods=["GET", "POST"])
@login_required
def presence():
    """Page de gestion des présences pour les enseignants."""
    if current_user.role != "enseignant":
        flash("Accès non autorisé.", "error")
        return redirect(url_for("main.index"))

    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()
    if not enseignant:
        flash("Profil enseignant non trouvé.", "error")
        return redirect(url_for("main.index"))

    filieres = []
    annees = []
    if enseignant.filieres_enseignees:
        try:
            data = json.loads(enseignant.filieres_enseignees)
            filieres = data.get("filieres", [])
            annees = data.get("annees", [])
        except Exception:
            pass

    matieres = Matiere.query.filter_by(enseignant_id=enseignant.id).all()

    selected_filiere = request.values.get("filiere")
    selected_annee = request.values.get("annee")
    selected_matiere = request.values.get("matiere", type=int)
    selected_date = request.values.get("date")

    etudiants = []

    if selected_filiere and selected_annee and selected_matiere and selected_date:
        matiere_obj = Matiere.query.get(selected_matiere)
        if matiere_obj and matiere_obj.filiere_id:
            filiere_obj = Filiere.query.get(matiere_obj.filiere_id)
            if filiere_obj and filiere_obj.nom in filieres:
                etudiants = Etudiant.query.filter_by(
                    filiere=filiere_obj.nom, annee=selected_annee
                ).all()

                if request.method == "POST":
                    from datetime import datetime as _dt

                    date_presence = _dt.strptime(selected_date, "%Y-%m-%d").date()
                    for etu in etudiants:
                        present = f"present_{etu.id}" in request.form
                        presence_rec = Presence.query.filter_by(
                            etudiant_id=etu.id,
                            matiere_id=selected_matiere,
                            date_presence=date_presence,
                        ).first()
                        if presence_rec:
                            presence_rec.present = present
                        else:
                            presence_rec = Presence(
                                etudiant_id=etu.id,
                                matiere_id=selected_matiere,
                                date_presence=date_presence,
                                present=present,
                            )
                            db.session.add(presence_rec)
                    db.session.commit()
                    flash("Présences enregistrées avec succès.", "success")
                    return redirect(request.url)

    return render_template(
        "enseignant/presence.html",
        filieres=filieres,
        annees=annees,
        matieres=matieres,
        selected_filiere=selected_filiere,
        selected_annee=selected_annee,
        selected_matiere=selected_matiere,
        selected_date=selected_date,
        etudiants=etudiants,
    )


@teachers_bp.route("/devoirs-a-corriger")
@login_required
def devoirs_a_corriger():
    """
    Permet à l'enseignant de consulter les devoirs à corriger.
    """
    if current_user.role != "enseignant":
        flash("Accès non autorisé.", "error")
        return redirect(url_for("main.index"))
    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()
    if not enseignant:
        flash("Profil enseignant non trouvé.", "error")
        return redirect(url_for("main.index"))
    # On récupère tous les devoirs de l'enseignant avec un fichier uploadé
    devoirs = (
        Devoir.query.filter_by(enseignant_id=enseignant.id)
        .filter(Devoir.fichier is not None)
        .all()
    )
    # Pour chaque devoir, on cherche l'étudiant qui a uploadé (si possible)
    devoirs_info = []
    for d in devoirs:
        # On suppose que le nom du fichier est unique par étudiant
        etudiant = None
        if d.fichier:
            # On tente de retrouver l'étudiant par le nom du fichier si possible
            etudiant = Etudiant.query.filter(
                Etudiant.user_id == d.enseignant_id
            ).first()
        devoirs_info.append(
            {"devoir": d, "nom_fichier": d.fichier, "etudiant": etudiant}
        )
    if request.is_json or request.args.get("format") == "json":
        return jsonify(
            {
                "success": True,
                "data": [
                    {
                        "devoir_id": info["devoir"].id,
                        "titre": info["devoir"].titre,
                        "filiere": info["devoir"].filiere,
                        "annee": info["devoir"].annee,
                        "etudiant_nom": (
                            info["etudiant"].nom if info["etudiant"] else "Inconnu"
                        ),
                        "fichier_url": (
                            f"/static/uploads/{info['nom_fichier']}"
                            if info["nom_fichier"]
                            else None
                        ),
                    }
                    for info in devoirs_info
                ],
            }
        )
    return render_template(
        "enseignant/devoirs_a_corriger.html", devoirs_info=devoirs_info
    )


@teachers_bp.route("/devoir/vus/<int:devoir_id>")
@login_required
def devoir_vus(devoir_id):
    """
    Permet à l'enseignant de consulter les étudiants qui ont consulté un devoir.
    """
    if current_user.role != "enseignant":
        flash("Accès non autorisé.", "error")
        return redirect(url_for("teachers.devoirs"))
    devoir = Devoir.query.get_or_404(devoir_id)
    if (
        devoir.enseignant_id
        != Enseignant.query.filter_by(user_id=current_user.id).first().id
    ):
        flash("Vous ne pouvez voir que vos propres devoirs.", "error")
        return redirect(url_for("teachers.devoirs"))
    vus = DevoirVu.query.filter_by(devoir_id=devoir_id).all()
    if request.is_json or request.args.get("format") == "json":
        return jsonify(
            {
                "success": True,
                "devoir_titre": devoir.titre,
                "vus_count": len(vus),
                "data": [
                    {
                        "nom": vu.etudiant.user.nom,
                        "prenom": vu.etudiant.user.prenom,
                        "sexe": vu.etudiant.user.sexe,
                        "date_vue": vu.date_vue.strftime("%d/%m/%Y %H:%M"),
                    }
                    for vu in vus
                ],
            }
        )
    return render_template("enseignant/devoir_vus.html", devoir=devoir, vus=vus)


@teachers_bp.route("/mes-etudiants")
@login_required
def manage_etudiants():
    """
    Permet à l'enseignant de consulter les étudiants inscrits dans les filières et années qu'il enseigne.
    """
    if current_user.role != "enseignant":
        flash("Accès non autorisé.", "error")
        return redirect(url_for("main.index"))

    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()
    if not enseignant:
        flash("Profil enseignant non trouvé.", "error")
        return redirect(url_for("main.index"))

    # Récupérer les filières et années enseignées
    filieres = []
    annees = []
    if enseignant.filieres_enseignees:
        try:
            data = json.loads(enseignant.filieres_enseignees)
            filieres = data.get("filieres", [])
            annees = data.get("annees", [])
        except Exception:
            pass

    if not filieres or not annees:
        flash("Aucune filière ou année assignée.", "warning")
        return render_template("enseignant/mes_etudiants.html", etudiants_data=[])

    selected_filiere = request.args.get("filiere")
    selected_annee = request.args.get("annee")
    if selected_filiere and selected_filiere not in filieres:
        selected_filiere = None
    if selected_annee and selected_annee not in annees:
        selected_annee = None

    # Récupérer les étudiants des filières/années enseignées
    etudiants_query = Etudiant.query.filter(
        Etudiant.filiere.in_(filieres), Etudiant.annee.in_(annees)
    )
    if selected_filiere:
        etudiants_query = etudiants_query.filter(Etudiant.filiere == selected_filiere)
    if selected_annee:
        etudiants_query = etudiants_query.filter(Etudiant.annee == selected_annee)
    etudiants = etudiants_query.all()

    # Récupérer les matières de l'enseignant
    matieres = Matiere.query.filter_by(enseignant_id=enseignant.id).all()
    matiere_id_defaut = matieres[0].id if matieres else 1

    # Préparer les données pour le template
    etudiants_data = []
    for etudiant in etudiants:
        user = User.query.get(etudiant.user_id)
        if user:
            etudiants_data.append((user, etudiant))

    # Statut de présence du jour avec la matière par défaut
    from datetime import date as _date

    today = _date.today()
    presence_status = {}
    for user, etudiant in etudiants_data:
        presence = Presence.query.filter_by(
            etudiant_id=etudiant.id, matiere_id=matiere_id_defaut, date_cours=today
        ).first()
        presence_status[etudiant.id] = bool(presence.present) if presence else False

    if request.is_json or request.args.get("format") == "json":
        return jsonify(
            {
                "success": True,
                "data": [
                    {
                        "user_id": user.id,
                        "etudiant_id": etudiant.id,
                        "nom": user.nom,
                        "prenom": user.prenom,
                        "filiere": etudiant.filiere,
                        "annee": etudiant.annee,
                        "present_aujourdhui": presence_status.get(etudiant.id, False),
                    }
                    for user, etudiant in etudiants_data
                ],
                "filieres": filieres,
                "annees": annees,
                "selected_filiere": selected_filiere,
                "selected_annee": selected_annee,
            }
        )

    return render_template(
        "enseignant/mes_etudiants.html",
        etudiants_data=etudiants_data,
        filieres_enseignees=filieres,
        annees_enseignees=annees,
        selected_filiere=selected_filiere,
        selected_annee=selected_annee,
        presence_status=presence_status,
        matiere_id_defaut=matiere_id_defaut,
    )


@teachers_bp.route("/mes-etudiants/presence", methods=["POST"])
@login_required
def set_etudiant_presence():
    """
    API pour définir la présence d'un étudiant.
    """
    if current_user.role != "enseignant":
        return jsonify({"success": False, "error": "Accès non autorisé"}), 403

    data = request.get_json(silent=True) or {}
    etudiant_id = data.get("etudiant_id")
    present = data.get("present")
    matiere_id = data.get("matiere_id")

    # Here we should implement the presence saving logic
    # Simplified for migration:
    try:
        # Check if presence exists
        presence_record = Presence.query.filter_by(
            etudiant_id=etudiant_id, matiere_id=matiere_id, date_cours=date.today()
        ).first()
        if presence_record:
            presence_record.present = present
        else:

            # Need to get matiere_nom
            matiere = Matiere.query.get(matiere_id)
            new_presence = Presence(
                etudiant_id=etudiant_id,
                matiere_id=matiere_id,
                matiere_nom=matiere.nom if matiere else "Inconnu",
                date_presence=date.today(),
                present=present,
                date_cours=date.today(),
            )
            db.session.add(new_presence)
        db.session.commit()

        # Notification si absence
        if not present:
            try:
                etu = Etudiant.query.get(etudiant_id)
                matiere = Matiere.query.get(matiere_id)
                NotificationService.notify_absence_recorded(etu, matiere, date.today())
            except Exception as e:
                current_app.logger.error(
                    f"Error in automatic absence notification: {e}"
                )

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@teachers_bp.route("/api/verifier-creneau")
@login_required
def verifier_creneau():
    """
    API pour vérifier si l'enseignant est dans un créneau horaire valide
    """
    if current_user.role != "enseignant":
        flash("Accès non autorisé", "error")
        return jsonify({"valide": False, "message": "Accès non autorisé"}), 403

    matiere_id = request.args.get("matiere_id", type=int)
    if not matiere_id:
        flash("ID de matière manquant", "error")
        return jsonify({"valide": False, "message": "ID de matière manquant"}), 400

    # Récupérer l'enseignant connecté
    enseignant = Enseignant.query.filter_by(user_id=current_user.id).first()
    if not enseignant:
        flash("Profil enseignant non trouvé", "error")
        return (
            jsonify({"valide": False, "message": "Profil enseignant non trouvé"}),
            404,
        )

    # Obtenir le jour actuel en français
    jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    jour_actuel = jours_fr[datetime.now().weekday()]  # 0 = Lundi, 1 = Mardi, etc.
    heure_actuelle = datetime.now().time()

    # Trouver le créneau de cours actuel pour cet enseignant et cette matière
    creneau = EmploiTemps.query.filter(
        EmploiTemps.enseignant_id == enseignant.id,
        EmploiTemps.matiere_id == matiere_id,
        EmploiTemps.jour == jour_actuel,
        EmploiTemps.heure_debut <= heure_actuelle,
        EmploiTemps.heure_fin >= heure_actuelle,
    ).first()

    if not creneau:
        flash("Aucun cours prévu à cette heure", "error")
        return jsonify({"valide": False, "message": "Aucun cours prévu à cette heure"})

    # Vérifier si on est dans la plage horaire autorisée (15 minutes avant/après le cours)
    marge = 15  # minutes
    debut_autorise = (
        datetime.combine(date.today(), creneau.heure_debut) - timedelta(minutes=marge)
    ).time()
    fin_autorisee = (
        datetime.combine(date.today(), creneau.heure_fin) + timedelta(minutes=marge)
    ).time()

    if not (debut_autorise <= heure_actuelle <= fin_autorisee):
        flash("Hors créneau autorisé", "error")
        return jsonify(
            {
                "valide": False,
                "message": f"Hors créneau autorisé (entre {debut_autorise.strftime('%H:%M')} et {fin_autorisee.strftime('%H:%M')})",
                "creneau": {
                    "heure_debut": creneau.heure_debut.strftime("%H:%M"),
                    "heure_fin": creneau.heure_fin.strftime("%H:%M"),
                    "salle": creneau.salle,
                },
            }
        )

    flash("Créneau valide", "success")

    return jsonify(
        {
            "valide": True,
            "message": f"Créneau valide - Salle: {creneau.salle}",
            "creneau": {
                "heure_debut": creneau.heure_debut.strftime("%H:%M"),
                "heure_fin": creneau.heure_fin.strftime("%H:%M"),
                "salle": creneau.salle,
            },
        }
    )
