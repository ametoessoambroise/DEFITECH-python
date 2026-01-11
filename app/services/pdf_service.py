from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime


class PDFService:
    @staticmethod
    def generate_registration_form(user, etudiant):
        """
        Génère la fiche d'inscription en PDF optimisée pour A4.
        """
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # --- En-tête ---
        c.setFont("Helvetica-Bold", 14)
        title = "FICHE D'INSCRIPTION LICENCE COURS DU JOURS"
        text_width = c.stringWidth(title, "Helvetica-Bold", 14)

        # Cadre autour du titre (plus compact)
        rect_x = (width - text_width) / 2 - 8
        rect_y = height - 60
        rect_w = text_width + 16
        rect_h = 24

        c.setLineWidth(1.5)
        c.rect(rect_x, rect_y, rect_w, rect_h)
        c.setLineWidth(0.8)
        c.rect(rect_x - 2, rect_y - 2, rect_w + 4, rect_h + 4)

        c.drawCentredString(width / 2, rect_y + 8, title)

        # --- Section ETUDIANT ---
        start_y = height - 100
        line_height = 20  # Réduit de 25 à 20

        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, start_y, "ETUDIANT")
        c.line(40, start_y - 3, 105, start_y - 3)

        def draw_field(label, value, x, y, dotted_width=200):
            c.setFont("Helvetica-Bold", 10)
            c.drawString(x, y, label)
            c.setFont("Helvetica", 10)

            label_w = c.stringWidth(label, "Helvetica-Bold", 10)
            start_dot = x + label_w + 3

            if value:
                c.drawString(start_dot + 3, y, str(value))

            c.setDash(1, 2)
            c.line(start_dot, y - 2, start_dot + dotted_width, y - 2)
            c.setDash([])

        # Ligne 1
        current_y = start_y - 25
        draw_field("NOM :", user.nom.upper(), 40, current_y, dotted_width=180)
        draw_field("PRENOMS :", user.prenom.title(), 300, current_y, dotted_width=250)

        # Ligne 2
        current_y -= line_height
        date_str = (
            user.date_naissance.strftime("%d/%m/%Y") if user.date_naissance else ""
        )
        draw_field("DATE DE NAISSANCE :", date_str, 40, current_y, dotted_width=140)
        draw_field(
            "LIEU DE NAISSANCE :",
            etudiant.lieu_naissance or "",
            280,
            current_y,
            dotted_width=200,
        )

        # Ligne 3
        current_y -= line_height
        draw_field(
            "NATIONALITE :", etudiant.nationalite or "", 40, current_y, dotted_width=140
        )

        # Checkboxes Sexe
        c.setFont("Helvetica-Bold", 10)
        c.drawString(280, current_y, "SEXE : M")
        c.rect(335, current_y - 2, 11, 11, fill=0)
        if user.sexe == "M":
            c.setFont("Helvetica-Bold", 12)
            c.drawString(337, current_y - 1, "X")

        c.setFont("Helvetica-Bold", 10)
        c.drawString(370, current_y, "F")
        c.rect(390, current_y - 2, 11, 11, fill=0)
        if user.sexe == "F":
            c.setFont("Helvetica-Bold", 12)
            c.drawString(392, current_y - 1, "X")

        # Ligne 4
        current_y -= line_height
        draw_field(
            "BAC (SERIE) :",
            etudiant.bac_serie or "",
            40,
            current_y,
            dotted_width=120,
        )
        draw_field(
            "ANNEE D'OBTENTION :",
            etudiant.bac_annee or "",
            260,
            current_y,
            dotted_width=130,
        )

        # Ligne 5
        current_y -= line_height
        draw_field(
            "ETABLISSEMENT DE PROVENANCE :",
            etudiant.etablissement_provenance or "",
            40,
            current_y,
            dotted_width=380,
        )

        # Inscription Annee
        current_y -= line_height + 5
        c.setFont("Helvetica-Bold", 10)

        c.drawString(40, current_y, "INSCRIPTION EN 1ère ANNEE")
        c.rect(192, current_y - 2, 13, 13)
        if etudiant.annee and "1" in str(etudiant.annee):
            c.setFont("Helvetica-Bold", 12)
            c.drawString(195, current_y + 1, "X")

        c.setFont("Helvetica-Bold", 10)
        c.drawString(220, current_y, "2ère ANNEE")
        c.rect(285, current_y - 2, 13, 13)
        if etudiant.annee and "2" in str(etudiant.annee):
            c.setFont("Helvetica-Bold", 12)
            c.drawString(288, current_y + 1, "X")

        c.setFont("Helvetica-Bold", 10)
        c.drawString(315, current_y, "3ère ANNEE")
        c.rect(380, current_y - 2, 13, 13)
        if etudiant.annee and "3" in str(etudiant.annee):
            c.setFont("Helvetica-Bold", 12)
            c.drawString(383, current_y + 1, "X")

        # --- Section FILIERE ---
        current_y -= 30
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, current_y, "FILIERE CHOISIE")
        c.line(40, current_y - 3, 135, current_y - 3)

        current_y -= 20
        col1_x = 40
        col2_x = 320

        # Récupération dynamique des filières
        try:
            from app.models.filiere import Filiere

            all_filieres = Filiere.query.order_by(Filiere.nom).all()
        except Exception:
            all_filieres = []

        filiere_names = [f.nom for f in all_filieres]

        if not filiere_names:
            # Fallback
            filiere_names = [
                "Génie Logiciel",
                "Systèmes et Réseaux",
                "BIG DATA (IA)",
                "Comptabilité Finance",
                "Publicité et Arts Graphique",
            ]

        # Split en deux colonnes
        mid_point = (len(filiere_names) + 1) // 2
        col1_filieres = filiere_names[:mid_point]
        col2_filieres = filiere_names[mid_point:]

        # Dessin Colonne 1
        y_col1 = current_y
        c.setFont("Helvetica", 9)
        for f in col1_filieres:
            c.drawString(col1_x + 8, y_col1, "> " + f)
            c.rect(col1_x + 180, y_col1 - 2, 11, 11)
            if etudiant.filiere and f.lower() in etudiant.filiere.lower():
                c.setFont("Helvetica-Bold", 11)
                c.drawString(col1_x + 182, y_col1, "X")
                c.setFont("Helvetica", 9)
            y_col1 -= 15

        # Dessin Colonne 2
        y_col2 = current_y
        for f in col2_filieres:
            c.drawString(col2_x + 8, y_col2, "> " + f)
            c.rect(col2_x + 200, y_col2 - 2, 11, 11)
            if etudiant.filiere and f.lower() in etudiant.filiere.lower():
                c.setFont("Helvetica-Bold", 11)
                c.drawString(col2_x + 202, y_col2, "X")
                c.setFont("Helvetica", 9)
            y_col2 -= 15

        current_y = min(y_col1, y_col2) - 15

        # Modalites
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, current_y, "MODALITE : Comptant")
        c.rect(145, current_y - 2, 11, 11)
        if etudiant.modalite_paiement == "Comptant":
            c.setFont("Helvetica-Bold", 12)
            c.drawString(147, current_y - 1, "X")

        c.setFont("Helvetica-Bold", 10)
        c.drawString(180, current_y, "3 Tranches")
        c.rect(245, current_y - 2, 11, 11)
        if etudiant.modalite_paiement == "3 Tranches":
            c.setFont("Helvetica-Bold", 12)
            c.drawString(247, current_y - 1, "X")

        c.setFont("Helvetica-Bold", 10)
        c.drawString(280, current_y, "7 Tranches")
        c.rect(345, current_y - 2, 11, 11)
        if etudiant.modalite_paiement == "7 Tranches":
            c.setFont("Helvetica-Bold", 12)
            c.drawString(347, current_y - 1, "X")

        current_y -= line_height
        draw_field(
            "AUTRES MODALITES :",
            etudiant.autres_modalites or "",
            40,
            current_y,
            dotted_width=380,
        )

        current_y -= line_height
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, current_y, "MODALITES CHOISIE (majuscule) :")
        c.setFont("Helvetica", 10)
        c.drawString(225, current_y, (etudiant.modalites_choisies or "").upper())
        c.setDash(1, 2)
        c.line(220, current_y - 2, 540, current_y - 2)
        c.setDash([])

        # Adresse etudiant
        current_y -= line_height
        draw_field(
            "ADRESSE (Etudiant) :",
            user.adresse or "",
            40,
            current_y,
            dotted_width=380,
        )

        current_y -= line_height
        draw_field("Tél :", user.telephone or "", 40, current_y, dotted_width=180)
        draw_field("E-mail :", user.email or "", 300, current_y, dotted_width=200)

        # --- Section PARENT ---
        current_y -= 28
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, current_y, "PARENT ou TUTEUR")
        c.line(40, current_y - 3, 150, current_y - 3)

        parent = etudiant.parents[0] if etudiant.parents else None

        current_y -= line_height
        p_nom = parent.nom if parent else ""
        p_prenom = parent.prenom if parent else ""
        draw_field("NOM :", p_nom.upper(), 40, current_y, dotted_width=180)
        draw_field("PRENOMS :", p_prenom.title(), 300, current_y, dotted_width=200)

        current_y -= line_height
        p_prof = parent.profession if parent else ""
        p_orga = getattr(parent, "organisme_employeur", "") if parent else ""

        draw_field("PROFESSION:", p_prof, 40, current_y, dotted_width=160)
        draw_field("ORGANISME :", p_orga, 280, current_y, dotted_width=180)

        current_y -= line_height
        p_adresse = parent.adresse if parent else ""
        draw_field("ADRESSE :", p_adresse, 40, current_y, dotted_width=460)

        current_y -= line_height
        p_tel_bur = parent.tel_bureau if parent else ""
        p_tel_dom = parent.tel_domicile if parent else ""
        p_email = parent.email if parent else ""

        draw_field("Tel. Bur:", p_tel_bur, 40, current_y, dotted_width=100)
        draw_field("Tel. Dom :", p_tel_dom, 190, current_y, dotted_width=100)
        draw_field("E-mail:", p_email, 360, current_y, dotted_width=140)

        # --- Footer ---
        current_y -= 35
        c.setFont("Helvetica", 10)
        c.drawString(40, current_y, "Signature Etudiant,")
        c.drawString(380, current_y, "Signature parent/tuteur")

        current_y -= 30
        date_jour = datetime.now().strftime("%d/%m/%Y")
        c.drawRightString(
            width - 40, current_y, f"Fait à Lomé, le {date_jour}................"
        )

        footer_y = 35
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(
            width / 2,
            footer_y + 10,
            "Sito Aéroport 01BP Lomé – Togo. Tél. (228)22 26 25 25 /22 26 24 24/ WhatsApp : +228 93 97 62 62",
        )

        c.setFont("Helvetica", 7.5)
        c.setFillColor(colors.blue)
        c.drawString(width / 2 - 120, footer_y, "Site: www.defitech.tg")
        c.drawString(width / 2 + 20, footer_y, "E-mail: defitech@defitech.tg")

        c.save()
        buffer.seek(0)
        return buffer
