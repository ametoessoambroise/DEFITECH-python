from datetime import datetime, timedelta
from enum import Enum
from app.extensions import db


class FlashcardStatus(Enum):
    """États possibles d'une carte mémoire dans le système de répétition espacée."""

    NEW = "new"  # Nouvelle carte, pas encore vue
    LEARNING = "learning"  # En cours d'apprentissage
    REVIEW = "review"  # En phase de révision
    RELEARN = "relearn"  # À réapprendre (réponse incorrecte après apprentissage)


class Flashcard(db.Model):
    """
    Modèle pour les cartes mémoire générées à partir du contenu des documents.
    Utilise un algorithme de répétition espacée (SRS) pour optimiser l'apprentissage.
    """

    __tablename__ = "flashcards"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    document_id = db.Column(
        db.Integer, db.ForeignKey("study_documents.id"), nullable=True
    )
    deck_id = db.Column(db.Integer, db.ForeignKey("flashcard_decks.id"), nullable=True)

    # Contenu de la carte
    front_text = db.Column(db.Text, nullable=False)  # Question ou terme
    back_text = db.Column(db.Text, nullable=False)  # Réponse ou définition
    tags = db.Column(db.String(255), nullable=True)  # Tags pour organiser les cartes

    # Métadonnées
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Paramètres de la répétition espacée (SRS - Spaced Repetition System)
    status = db.Column(db.String(20), default=FlashcardStatus.NEW.value, nullable=False)
    ease_factor = db.Column(
        db.Float, default=2.5
    )  # Facteur de facilité (affecte l'espacement des révisions)
    interval = db.Column(
        db.Integer, default=0
    )  # Intervalle en jours avant la prochaine révision
    due_date = db.Column(db.DateTime, nullable=True)  # Date de la prochaine révision

    # Statistiques
    review_count = db.Column(db.Integer, default=0)  # Nombre total de révisions
    correct_count = db.Column(db.Integer, default=0)  # Nombre de réponses correctes

    # Relations
    user = db.relationship("User", backref=db.backref("flashcards", lazy=True))
    reviews = db.relationship(
        "FlashcardReview", backref="flashcard", lazy=True, cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        super(Flashcard, self).__init__(**kwargs)
        self.due_date = datetime.utcnow()  # Par défaut, la carte est due immédiatement

    def process_review(self, quality, review_time=None):
        """
        Traite une révision de la carte selon l'algorithme SM-2.

        Args:
            quality: Qualité de la réponse (0-5)
                     0 - Pas du tout retenu
                     1 - Très difficile (mauvaise réponse)
                     2 - Difficile (bonne réponse avec difficulté)
                     3 - Bonne réponse
                     4 - Facile
                     5 - Très facile
            review_time: Moment de la révision (utile pour les tests)
        """
        if review_time is None:
            review_time = datetime.utcnow()

        # Créer un nouvel enregistrement de révision
        review = FlashcardReview(
            flashcard_id=self.id,
            user_id=self.user_id,
            quality=quality,
            reviewed_at=review_time,
        )
        db.session.add(review)

        # Mettre à jour les statistiques
        self.review_count += 1
        if quality >= 3:  # Si la réponse est correcte (3-5)
            self.correct_count += 1

        # Mettre à jour le statut
        if self.status == FlashcardStatus.NEW.value:
            self._process_new_card(quality)
        else:
            self._process_review(quality)

        # Mettre à jour la date de révision
        self.due_date = review_time + timedelta(days=self.interval)
        self.updated_at = datetime.utcnow()

        db.session.commit()
        return self

    def _process_new_card(self, quality):
        """Traite une nouvelle carte (première révision)."""
        if quality >= 3:  # Bonne réponse
            self.status = FlashcardStatus.LEARNING.value
            self.interval = 1  # Révision le lendemain
            self.ease_factor = max(1.3, self.ease_factor)  # Facteur minimum de 1.3
        else:
            # Reste en statut NEW pour être revue le même jour
            self.interval = 0  # À revoir le même jour

    def _process_review(self, quality):
        """Traite une révision d'une carte existante."""
        if quality < 3:  # Mauvaise réponse
            self.status = FlashcardStatus.RELEARN.value
            self.interval = 0  # À revoir le même jour
            # Réduire le facteur de facilité (minimum 1.3)
            self.ease_factor = max(1.3, self.ease_factor - 0.15)
        else:
            # Mettre à jour le facteur de facilité
            if quality == 3:  # Bonne réponse
                self.ease_factor += -0.14 + (0.1 * (5 - 3))
            elif quality == 4:  # Facile
                self.ease_factor += 0.10
            elif quality == 5:  # Très facile
                self.ease_factor += 0.15

            # Limiter le facteur de facilité entre 1.3 et 2.5
            self.ease_factor = max(1.3, min(2.5, self.ease_factor))

            # Mettre à jour l'intervalle
            if self.status == FlashcardStatus.LEARNING.value:
                if (
                    self.review_count >= 3
                ):  # Après 3 bonnes réponses, passer en mode révision
                    self.status = FlashcardStatus.REVIEW.value
                    self.interval = max(1, int(self.interval * self.ease_factor))
                else:
                    self.interval = 1  # Révision le lendemain
            else:  # En mode révision
                self.interval = max(1, int(self.interval * self.ease_factor))

    def to_dict(self, include_reviews=False):
        """Convertit la carte mémoire en dictionnaire."""
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "document_id": self.document_id,
            "front_text": self.front_text,
            "back_text": self.back_text,
            "tags": self.tags.split(",") if self.tags else [],
            "status": self.status,
            "ease_factor": self.ease_factor,
            "interval": self.interval,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "review_count": self.review_count,
            "correct_count": self.correct_count,
            "accuracy": (
                round((self.correct_count / self.review_count * 100), 1)
                if self.review_count > 0
                else 0
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_reviews and self.reviews:
            result["reviews"] = [r.to_dict() for r in self.reviews]

        return result

    @classmethod
    def get_due_cards(cls, user_id, limit=20):
        """Récupère les cartes qui sont dues pour révision."""
        now = datetime.utcnow()
        return (
            cls.query.filter(
                cls.user_id == user_id, (cls.due_date <= now) | (cls.due_date.is_(None))
            )
            .order_by(cls.due_date.asc())
            .limit(limit)
            .all()
        )

    def __repr__(self):
        return f"<Flashcard {self.id} (User: {self.user_id})>"


class FlashcardReview(db.Model):
    """
    Modèle pour suivre les révisions des cartes mémoire.
    """

    __tablename__ = "flashcard_reviews"

    id = db.Column(db.Integer, primary_key=True)
    flashcard_id = db.Column(db.Integer, db.ForeignKey("flashcards.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Qualité de la réponse (0-5)
    quality = db.Column(db.Integer, nullable=False)

    # Temps de révision
    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    time_spent_seconds = db.Column(
        db.Integer, default=0
    )  # Temps passé sur la carte en secondes

    # Relations
    user = db.relationship("User", backref=db.backref("flashcard_reviews", lazy=True))

    def to_dict(self):
        """Convertit la révision en dictionnaire."""
        return {
            "id": self.id,
            "flashcard_id": self.flashcard_id,
            "user_id": self.user_id,
            "quality": self.quality,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "time_spent_seconds": self.time_spent_seconds,
        }

    def __repr__(self):
        return f"<FlashcardReview {self.id} (Flashcard: {self.flashcard_id}, Quality: {self.quality})>"
