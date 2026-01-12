"""
Registry des outils disponibles pour l'extension VS Code Intelitech.

Ce module définit tous les outils que l'IA peut demander via l'extension VS Code.
Ces outils sont exécutés localement sur la machine de l'utilisateur (pas sur le serveur).

Format de demande: [INTELLITECH_TOOL: tool_name, {json_params}]
Format de réponse: L'extension exécute l'outil et renvoie les résultats dans la prochaine requête.

Architecture:
1. L'IA Gemini détecte qu'elle a besoin d'un outil et génère [INTELLITECH_TOOL: ...]
2. Le serveur Flask parse cette demande et la renvoie dans la réponse JSON
3. L'extension VS Code exécute l'outil localement
4. L'extension renvoie les résultats dans la prochaine requête à l'API
5. Le serveur inclut ces résultats dans le contexte pour Gemini
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class ToolCategory(Enum):
    """Catégories d'outils disponibles"""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_SEARCH = "file_search"
    SYSTEM = "system"
    WEB = "web"
    MEMORY = "memory"
    TASK = "task"


@dataclass
class ToolDefinition:
    """Définition d'un outil disponible"""
    name: str
    category: ToolCategory
    description: str
    parameters: Dict[str, Any]  # Schéma JSON des paramètres
    example: Dict[str, Any]  # Exemple d'utilisation
    security_level: str  # "safe", "warning", "dangerous"


class IntelitechToolsRegistry:
    """Registry centralisée de tous les outils Intelitech"""

    # ========================================
    # OUTILS DE LECTURE DE FICHIERS
    # ========================================

    READ_FILE = ToolDefinition(
        name="read_file",
        category=ToolCategory.FILE_READ,
        description="Lit le contenu d'un fichier spécifique",
        parameters={
            "file_path": {"type": "string", "required": True, "description": "Chemin absolu du fichier"},
            "limit": {"type": "number", "required": False, "description": "Nombre de lignes à lire"},
            "offset": {"type": "number", "required": False, "description": "Ligne de départ (1-indexé)"}
        },
        example={
            "file_path": "c:\\Users\\LENOVO\\Desktop\\project\\src\\main.ts",
            "limit": 50,
            "offset": 1
        },
        security_level="safe"
    )

    READ_NOTEBOOK = ToolDefinition(
        name="read_notebook",
        category=ToolCategory.FILE_READ,
        description="Lit et analyse un fichier Jupyter Notebook (.ipynb)",
        parameters={
            "absolute_path": {"type": "string", "required": True, "description": "Chemin absolu du notebook"}
        },
        example={
            "absolute_path": "c:\\Users\\LENOVO\\Desktop\\project\\notebook.ipynb"
        },
        security_level="safe"
    )

    LIST_DIR = ToolDefinition(
        name="list_dir",
        category=ToolCategory.FILE_READ,
        description="Liste les fichiers et dossiers dans un répertoire",
        parameters={
            "directory_path": {"type": "string", "required": True, "description": "Chemin absolu du répertoire"}
        },
        example={
            "directory_path": "c:\\Users\\LENOVO\\Desktop\\project\\src"
        },
        security_level="safe"
    )

    FIND_BY_NAME = ToolDefinition(
        name="find_by_name",
        category=ToolCategory.FILE_SEARCH,
        description="Recherche des fichiers/dossiers par nom ou pattern",
        parameters={
            "search_directory": {"type": "string", "required": True, "description": "Répertoire de recherche"},
            "pattern": {"type": "string", "required": True, "description": "Pattern de recherche (glob)"},
            "type": {"type": "string", "required": False, "enum": ["file", "directory", "any"], "description": "Type de résultat"},
            "max_depth": {"type": "number", "required": False, "description": "Profondeur max de recherche"},
            "extensions": {"type": "array", "required": False, "items": {"type": "string"}, "description": "Extensions de fichiers à inclure"}
        },
        example={
            "search_directory": "c:\\Users\\LENOVO\\Desktop\\project",
            "pattern": "*.ts",
            "type": "file",
            "extensions": ["ts", "tsx"]
        },
        security_level="safe"
    )

    GREP_SEARCH = ToolDefinition(
        name="grep_search",
        category=ToolCategory.FILE_SEARCH,
        description="Recherche avancée de texte dans les fichiers",
        parameters={
            "search_path": {"type": "string", "required": True, "description": "Chemin de recherche"},
            "query": {"type": "string", "required": True, "description": "Texte ou regex à rechercher"},
            "case_sensitive": {"type": "boolean", "required": False, "description": "Sensible à la casse"},
            "fixed_strings": {"type": "boolean", "required": False, "description": "Traitement littéral (pas de regex)"},
            "includes": {"type": "array", "required": False, "items": {"type": "string"}, "description": "Patterns de fichiers à inclure"},
            "match_per_line": {"type": "boolean", "required": False, "description": "Afficher le contexte des matches"}
        },
        example={
            "search_path": "c:\\Users\\LENOVO\\Desktop\\project\\src",
            "query": "function.*async",
            "includes": ["*.ts", "*.js"],
            "match_per_line": True
        },
        security_level="safe"
    )

    # ========================================
    # OUTILS D'ÉDITION DE FICHIERS
    # ========================================

    EDIT = ToolDefinition(
        name="edit",
        category=ToolCategory.FILE_WRITE,
        description="Effectue un remplacement de texte exact dans un fichier",
        parameters={
            "file_path": {"type": "string", "required": True, "description": "Chemin absolu du fichier"},
            "old_string": {"type": "string", "required": True, "description": "Texte à remplacer (doit être exact)"},
            "new_string": {"type": "string", "required": True, "description": "Texte de remplacement"},
            "explanation": {"type": "string", "required": True, "description": "Description de la modification"},
            "replace_all": {"type": "boolean", "required": False, "description": "Remplacer toutes les occurrences"}
        },
        example={
            "file_path": "c:\\Users\\LENOVO\\Desktop\\project\\src\\config.ts",
            "old_string": "const apiUrl = 'localhost:3000'",
            "new_string": "const apiUrl = 'https://api.example.com'",
            "explanation": "Mise à jour de l'URL de l'API pour la production",
            "replace_all": False
        },
        security_level="warning"
    )

    MULTI_EDIT = ToolDefinition(
        name="multi_edit",
        category=ToolCategory.FILE_WRITE,
        description="Effectue plusieurs modifications dans un seul fichier",
        parameters={
            "file_path": {"type": "string", "required": True, "description": "Chemin absolu du fichier"},
            "edits": {
                "type": "array",
                "required": True,
                "items": {
                    "type": "object",
                    "properties": {
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"}
                    },
                    "required": ["old_string", "new_string"]
                },
                "description": "Liste des modifications"
            },
            "explanation": {"type": "string", "required": True, "description": "Description générale"}
        },
        example={
            "file_path": "c:\\Users\\LENOVO\\Desktop\\project\\src\\index.ts",
            "explanation": "Refactorisation des imports et ajout de logging",
            "edits": [
                {
                    "old_string": "import { User } from './user'",
                    "new_string": "import { User, Logger } from './types'"
                },
                {
                    "old_string": "console.log(data)",
                    "new_string": "logger.info(data)"
                }
            ]
        },
        security_level="warning"
    )

    EDIT_NOTEBOOK = ToolDefinition(
        name="edit_notebook",
        category=ToolCategory.FILE_WRITE,
        description="Modifie une cellule spécifique d'un notebook Jupyter",
        parameters={
            "absolute_path": {"type": "string", "required": True, "description": "Chemin du notebook"},
            "cell_number": {"type": "number", "required": False, "description": "Numéro de la cellule (0-indexé)"},
            "cell_id": {"type": "string", "required": False, "description": "ID de la cellule"},
            "new_source": {"type": "string", "required": True, "description": "Nouveau contenu de la cellule"},
            "edit_mode": {"type": "string", "required": False, "enum": ["replace", "insert", "delete"], "description": "Mode d'édition"}
        },
        example={
            "absolute_path": "c:\\Users\\LENOVO\\Desktop\\project\\analysis.ipynb",
            "cell_number": 2,
            "new_source": "import pandas as pd\nimport numpy as np\n\ndf = pd.read_csv('data.csv')",
            "edit_mode": "replace"
        },
        security_level="warning"
    )

    WRITE_TO_FILE = ToolDefinition(
        name="write_to_file",
        category=ToolCategory.FILE_WRITE,
        description="Crée un nouveau fichier avec du contenu",
        parameters={
            "target_file": {"type": "string", "required": True, "description": "Chemin du fichier à créer"},
            "code_content": {"type": "string", "required": True, "description": "Contenu du fichier"},
            "empty_file": {"type": "boolean", "required": True, "description": "false pour ajouter du contenu"}
        },
        example={
            "target_file": "src/utils/helper.ts",
            "code_content": "export function formatDate(date: Date): string {\n  return date.toISOString();\n}",
            "empty_file": False
        },
        security_level="warning"
    )

    # ========================================
    # OUTILS SYSTÈME ET TERMINAL
    # ========================================

    BASH = ToolDefinition(
        name="bash",
        category=ToolCategory.SYSTEM,
        description="Exécute des commandes shell/terminal",
        parameters={
            "command_line": {"type": "string", "required": True, "description": "Commande à exécuter"},
            "cwd": {"type": "string", "required": True, "description": "Répertoire de travail"},
            "background": {"type": "boolean", "required": False, "description": "Exécution en arrière-plan"},
            "safe_to_auto_run": {"type": "boolean", "required": False, "description": "Exécution automatique sans confirmation"},
            "wait_ms_before_async": {"type": "number", "required": False, "description": "Délai avant mode async"}
        },
        example={
            "command_line": "npm install",
            "cwd": "c:\\Users\\LENOVO\\Desktop\\project",
            "safe_to_auto_run": False
        },
        security_level="dangerous"
    )

    COMMAND_STATUS = ToolDefinition(
        name="command_status",
        category=ToolCategory.SYSTEM,
        description="Vérifie le statut d'une commande en arrière-plan",
        parameters={
            "command_id": {"type": "string", "required": True, "description": "ID de la commande"},
            "output_character_count": {"type": "number", "required": True, "description": "Nombre de caractères à lire"},
            "wait_duration_seconds": {"type": "number", "required": False, "description": "Temps d'attente max"}
        },
        example={
            "command_id": "cmd_123456",
            "output_character_count": 1000,
            "wait_duration_seconds": 5
        },
        security_level="safe"
    )

    # ========================================
    # OUTILS WEB ET RÉSEAU
    # ========================================

    MCP_FETCH = ToolDefinition(
        name="mcp0_fetch",
        category=ToolCategory.WEB,
        description="Récupère le contenu d'une URL web",
        parameters={
            "url": {"type": "string", "required": True, "description": "URL à récupérer"},
            "max_length": {"type": "number", "required": False, "description": "Taille max du contenu"},
            "raw": {"type": "boolean", "required": False, "description": "HTML brut ou simplifié"},
            "start_index": {"type": "number", "required": False, "description": "Position de départ"}
        },
        example={
            "url": "https://example.com/documentation",
            "max_length": 10000,
            "raw": False
        },
        security_level="safe"
    )

    SEARCH_WEB = ToolDefinition(
        name="search_web",
        category=ToolCategory.WEB,
        description="Recherche web avec résultats",
        parameters={
            "query": {"type": "string", "required": True, "description": "Requête de recherche"},
            "domain": {"type": "string", "required": False, "description": "Domaine à prioriser"}
        },
        example={
            "query": "Python async await tutorial",
            "domain": "docs.python.org"
        },
        security_level="safe"
    )

    # ========================================
    # OUTILS DE GESTION DE MÉMOIRE
    # ========================================

    CREATE_MEMORY = ToolDefinition(
        name="create_memory",
        category=ToolCategory.MEMORY,
        description="Sauvegarde du contexte important",
        parameters={
            "action": {"type": "string", "required": True, "enum": ["create", "update", "delete"], "description": "Action à effectuer"},
            "title": {"type": "string", "required": True, "description": "Titre du mémoire"},
            "content": {"type": "string", "required": True, "description": "Contenu"},
            "corpus_names": {"type": "array", "required": True, "items": {"type": "string"}, "description": "Espaces de travail concernés"},
            "tags": {"type": "array", "required": True, "items": {"type": "string"}, "description": "Étiquettes"},
            "user_triggered": {"type": "boolean", "required": True, "description": "Déclenché par l'utilisateur"},
            "id": {"type": "string", "required": False, "description": "ID pour update/delete"}
        },
        example={
            "action": "create",
            "title": "Architecture du projet",
            "content": "Le projet utilise React + TypeScript...",
            "corpus_names": ["my-project"],
            "tags": ["architecture", "react"],
            "user_triggered": False
        },
        security_level="safe"
    )

    # ========================================
    # OUTILS DE GESTION DE TÂCHES
    # ========================================

    TODO_LIST = ToolDefinition(
        name="todo_list",
        category=ToolCategory.TASK,
        description="Crée et gère des listes de tâches",
        parameters={
            "todos": {
                "type": "array",
                "required": True,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "content": {"type": "string"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                        "priority": {"type": "string", "enum": ["high", "medium", "low"]}
                    },
                    "required": ["id", "content", "status"]
                },
                "description": "Liste des tâches"
            }
        },
        example={
            "todos": [
                {
                    "id": "task_1",
                    "content": "Implémenter la fonction login",
                    "status": "pending",
                    "priority": "high"
                },
                {
                    "id": "task_2",
                    "content": "Ajouter les tests unitaires",
                    "status": "in_progress",
                    "priority": "medium"
                }
            ]
        },
        security_level="safe"
    )

    # ========================================
    # REGISTRY ET MÉTHODES UTILITAIRES
    # ========================================

    @classmethod
    def get_all_tools(cls) -> List[ToolDefinition]:
        """Retourne la liste de tous les outils disponibles"""
        return [
            # Lecture
            cls.READ_FILE,
            cls.READ_NOTEBOOK,
            cls.LIST_DIR,
            cls.FIND_BY_NAME,
            cls.GREP_SEARCH,
            # Édition
            cls.EDIT,
            cls.MULTI_EDIT,
            cls.EDIT_NOTEBOOK,
            cls.WRITE_TO_FILE,
            # Système
            cls.BASH,
            cls.COMMAND_STATUS,
            # Web
            cls.MCP_FETCH,
            cls.SEARCH_WEB,
            # Mémoire
            cls.CREATE_MEMORY,
            # Tâches
            cls.TODO_LIST,
        ]

    @classmethod
    def get_tool_by_name(cls, tool_name: str) -> Optional[ToolDefinition]:
        """Retourne la définition d'un outil par son nom"""
        for tool in cls.get_all_tools():
            if tool.name == tool_name:
                return tool
        return None

    @classmethod
    def get_tools_by_category(cls, category: ToolCategory) -> List[ToolDefinition]:
        """Retourne tous les outils d'une catégorie"""
        return [tool for tool in cls.get_all_tools() if tool.category == category]

    @classmethod
    def get_tools_documentation(cls) -> str:
        """
        Génère la documentation complète des outils pour le prompt système.
        Format optimisé pour être inclus dans le system_prompt.
        """
        doc_lines = [
            "╔════════════════════════════════════════════════════════════════════════════╗",
            "║            OUTILS DISPONIBLES POUR L'EXTENSION VS CODE INTELITECH          ║",
            "╚════════════════════════════════════════════════════════════════════════════╝",
            "",
            "⚠️ IMPORTANT: Ces outils sont exécutés LOCALEMENT sur la machine de l'utilisateur.",
            "Format de demande: [INTELLITECH_TOOL: nom_outil, {paramètres_json}]",
            "L'extension VS Code exécutera l'outil et renverra les résultats dans la prochaine requête.",
            "",
        ]

        # Grouper par catégorie
        categories = {
            ToolCategory.FILE_READ: "📖 OUTILS DE LECTURE DE FICHIERS",
            ToolCategory.FILE_WRITE: "✏️ OUTILS D'ÉDITION DE FICHIERS",
            ToolCategory.FILE_SEARCH: "🔍 OUTILS DE RECHERCHE DE FICHIERS",
            ToolCategory.SYSTEM: "🖥️ OUTILS SYSTÈME ET TERMINAL",
            ToolCategory.WEB: "🌐 OUTILS WEB ET RÉSEAU",
            ToolCategory.MEMORY: "🧠 OUTILS DE GESTION DE MÉMOIRE",
            ToolCategory.TASK: "📋 OUTILS DE GESTION DE TÂCHES",
        }

        for category, category_title in categories.items():
            tools = cls.get_tools_by_category(category)
            if not tools:
                continue

            doc_lines.append(f"\n{category_title}")
            doc_lines.append("=" * 80)
            doc_lines.append("")

            for tool in tools:
                # En-tête de l'outil
                security_icon = {
                    "safe": "✅",
                    "warning": "⚠️",
                    "dangerous": "🔴"
                }.get(tool.security_level, "❓")

                doc_lines.append(f"### {security_icon} `{tool.name}`")
                doc_lines.append(f"**Description:** {tool.description}")
                doc_lines.append("")

                # Paramètres
                doc_lines.append("**Paramètres:**")
                for param_name, param_spec in tool.parameters.items():
                    required = param_spec.get("required", False)
                    param_type = param_spec.get("type", "string")
                    param_desc = param_spec.get("description", "")
                    required_mark = " (obligatoire)" if required else " (optionnel)"
                    doc_lines.append(f"- `{param_name}` ({param_type}){required_mark}: {param_desc}")

                doc_lines.append("")

                # Exemple
                import json
                example_str = json.dumps(tool.example, indent=2, ensure_ascii=False)
                doc_lines.append("**Exemple:**")
                doc_lines.append("```json")
                doc_lines.append(example_str)
                doc_lines.append("```")
                doc_lines.append("")

                # Format de demande
                doc_lines.append("**Format de demande:**")
                example_request = json.dumps(tool.example, ensure_ascii=False)
                doc_lines.append(f"`[INTELLITECH_TOOL: {tool.name}, {example_request}]`")
                doc_lines.append("")

        # Instructions d'utilisation
        doc_lines.append("")
        doc_lines.append("=" * 80)
        doc_lines.append("📝 INSTRUCTIONS D'UTILISATION")
        doc_lines.append("=" * 80)
        doc_lines.append("")
        doc_lines.append("1. Détecter le besoin: Si l'utilisateur demande une action qui nécessite un outil,")
        doc_lines.append("   inclure la demande d'outil dans ta réponse au format [INTELLITECH_TOOL: ...]")
        doc_lines.append("")
        doc_lines.append("2. Format strict: Le format doit être valide JSON pour les paramètres")
        doc_lines.append("")
        doc_lines.append("3. Un seul outil par demande: Chaque [INTELLITECH_TOOL: ...] est indépendant")
        doc_lines.append("")
        doc_lines.append("4. Attente des résultats: L'extension exécutera l'outil et renverra les résultats")
        doc_lines.append("   dans la prochaine requête. Tu pourras alors les utiliser dans ta réponse.")
        doc_lines.append("")
        doc_lines.append("5. Sécurité: Les outils avec niveau 'dangerous' (comme bash) nécessitent")
        doc_lines.append("   une confirmation explicite de l'utilisateur avant exécution.")
        doc_lines.append("")

        return "\n".join(doc_lines)
