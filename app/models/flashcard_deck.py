from datetime import datetime
from app.extensions import db


class FlashcardDeck(db.Model):
    """Modèle pour les decks (paquets) de flashcards"""

    __tablename__ = "flashcard_decks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Informations
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default="#3B82F6")  # Couleur hex pour UI

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    user = db.relationship("User", backref="flashcard_decks")
    flashcards = db.relationship("Flashcard", backref="deck", lazy="dynamic")

    @property
    def card_count(self):
        """Nombre de cartes dans le deck"""
        return self.flashcards.count()

    @property
    def due_card_count(self):
        """Nombre de cartes à réviser"""
        from datetime import datetime
        from app.models.flashcard import Flashcard

        return self.flashcards.filter(
            (Flashcard.due_date <= datetime.utcnow()) | (Flashcard.due_date.is_(None))
        ).count()

    def to_dict(self):
        """Convertit le deck en dictionnaire"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "card_count": self.card_count,
            "due_card_count": self.due_card_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<FlashcardDeck {self.id}: {self.name}>"
