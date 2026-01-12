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
        description="Affiche le contenu d'un fichier (par exemple: lire un fichier TypeScript, Python, JSON, etc.)",
        parameters={
            "file_path": {"type": "string", "required": True, "description": "Nom du fichier à lire (exemple: 'src/main.ts' ou 'config.json')"},
            "limit": {"type": "number", "required": False, "description": "Nombre maximum de lignes à afficher (utile pour les gros fichiers)"},
            "offset": {"type": "number", "required": False, "description": "Commencer à partir de quelle ligne (par défaut: ligne 1)"}
        },
        example={
            "file_path": "src/app.py",
            "limit": 100
        },
        security_level="safe"
    )

    READ_NOTEBOOK = ToolDefinition(
        name="read_notebook",
        category=ToolCategory.FILE_READ,
        description="Ouvre et lit un notebook Jupyter pour voir son code et ses résultats",
        parameters={
            "absolute_path": {"type": "string", "required": True, "description": "Nom du fichier notebook (exemple: 'analysis.ipynb' ou 'data_exploration.ipynb')"}
        },
        example={
            "absolute_path": "data_analysis.ipynb"
        },
        security_level="safe"
    )

    LIST_DIR = ToolDefinition(
        name="list_dir",
        category=ToolCategory.FILE_READ,
        description="Affiche la liste de tous les fichiers et dossiers dans un répertoire",
        parameters={
            "directory_path": {"type": "string", "required": True, "description": "Chemin du dossier à explorer (exemple: 'src' ou 'c:\\projet\\backend')"}
        },
        example={
            "directory_path": "src"
        },
        security_level="safe"
    )

    FIND_BY_NAME = ToolDefinition(
        name="find_by_name",
        category=ToolCategory.FILE_SEARCH,
        description="Recherche des fichiers par leur nom (comme chercher 'tous les fichiers .tsx' ou 'config*')",
        parameters={
            "search_directory": {"type": "string", "required": True, "description": "Dossier où chercher"},
            "pattern": {"type": "string", "required": True, "description": "Nom ou motif à chercher (exemple: '*.py' pour tous les fichiers Python, 'test*' pour les fichiers commençant par 'test')"},
            "type": {"type": "string", "required": False, "enum": ["file", "directory", "any"], "description": "Chercher des fichiers, des dossiers, ou les deux"},
            "max_depth": {"type": "number", "required": False, "description": "Profondeur de recherche (1 = dossier actuel uniquement, 2 = inclure les sous-dossiers, etc.)"},
            "extensions": {"type": "array", "required": False, "items": {"type": "string"}, "description": "Extensions de fichiers spécifiques (exemple: ['ts', 'tsx', 'js'])"}
        },
        example={
            "search_directory": "src",
            "pattern": "*.ts",
            "type": "file"
        },
        security_level="safe"
    )

    GREP_SEARCH = ToolDefinition(
        name="grep_search",
        category=ToolCategory.FILE_SEARCH,
        description="Recherche du texte à l'intérieur des fichiers (comme Ctrl+F dans tout le projet)",
        parameters={
            "search_path": {"type": "string", "required": True, "description": "Dossier où chercher"},
            "query": {"type": "string", "required": True, "description": "Texte à rechercher (exemple: 'function login' ou 'TODO')"},
            "case_sensitive": {"type": "boolean", "required": False, "description": "Respecter majuscules/minuscules (true) ou ignorer (false)"},
            "fixed_strings": {"type": "boolean", "required": False, "description": "Chercher le texte exact (true) ou permettre les expressions régulières (false)"},
            "includes": {"type": "array", "required": False, "items": {"type": "string"}, "description": "Chercher uniquement dans certains types de fichiers (exemple: ['*.py', '*.txt'])"},
            "match_per_line": {"type": "boolean", "required": False, "description": "Afficher le contexte autour de chaque résultat"}
        },
        example={
            "search_path": "src",
            "query": "async function",
            "includes": ["*.ts", "*.js"]
        },
        security_level="safe"
    )

    # ========================================
    # OUTILS D'ÉDITION DE FICHIERS
    # ========================================

    EDIT = ToolDefinition(
        name="edit",
        category=ToolCategory.FILE_WRITE,
        description="Remplace un morceau de code par un autre dans un fichier (comme un chercher-remplacer)",
        parameters={
            "file_path": {"type": "string", "required": True, "description": "Fichier à modifier"},
            "old_string": {"type": "string", "required": True, "description": "Code actuel à remplacer (doit être exactement identique)"},
            "new_string": {"type": "string", "required": True, "description": "Nouveau code à mettre à la place"},
            "explanation": {"type": "string", "required": True, "description": "Explication de pourquoi tu fais cette modification"},
            "replace_all": {"type": "boolean", "required": False, "description": "Remplacer toutes les occurrences (true) ou seulement la première (false)"}
        },
        example={
            "file_path": "src/config.ts",
            "old_string": "const port = 3000",
            "new_string": "const port = 8080",
            "explanation": "Changement du port pour éviter les conflits",
            "replace_all": False
        },
        security_level="warning"
    )

    MULTI_EDIT = ToolDefinition(
        name="multi_edit",
        category=ToolCategory.FILE_WRITE,
        description="Fait plusieurs modifications dans le même fichier en une seule fois",
        parameters={
            "file_path": {"type": "string", "required": True, "description": "Fichier à modifier"},
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
                "description": "Liste de toutes les modifications à faire"
            },
            "explanation": {"type": "string", "required": True, "description": "Explication globale des modifications"}
        },
        example={
            "file_path": "src/app.py",
            "explanation": "Ajout de logging et correction du nom de variable",
            "edits": [
                {
                    "old_string": "print(data)",
                    "new_string": "logger.info(data)"
                },
                {
                    "old_string": "usr_name",
                    "new_string": "username"
                }
            ]
        },
        security_level="warning"
    )

    EDIT_NOTEBOOK = ToolDefinition(
        name="edit_notebook",
        category=ToolCategory.FILE_WRITE,
        description="Modifie une cellule spécifique dans un notebook Jupyter",
        parameters={
            "absolute_path": {"type": "string", "required": True, "description": "Nom du notebook"},
            "cell_number": {"type": "number", "required": False, "description": "Numéro de la cellule à modifier (commence à 0)"},
            "cell_id": {"type": "string", "required": False, "description": "ID unique de la cellule (alternative au numéro)"},
            "new_source": {"type": "string", "required": True, "description": "Nouveau code de la cellule"},
            "edit_mode": {"type": "string", "required": False, "enum": ["replace", "insert", "delete"], "description": "Action à faire: remplacer, insérer, ou supprimer"}
        },
        example={
            "absolute_path": "analysis.ipynb",
            "cell_number": 0,
            "new_source": "import pandas as pd\nimport numpy as np",
            "edit_mode": "replace"
        },
        security_level="warning"
    )

    WRITE_TO_FILE = ToolDefinition(
        name="write_to_file",
        category=ToolCategory.FILE_WRITE,
        description="Crée un nouveau fichier avec du contenu",
        parameters={
            "target_file": {"type": "string", "required": True, "description": "Nom et emplacement du fichier à créer (exemple: 'src/utils.py')"},
            "code_content": {"type": "string", "required": True, "description": "Tout le contenu à mettre dans le fichier"},
            "empty_file": {"type": "boolean", "required": True, "description": "false pour ajouter du contenu, true pour créer un fichier vide"}
        },
        example={
            "target_file": "src/helpers.py",
            "code_content": "def hello():\n    print('Hello World!')",
            "empty_file": False
        },
        security_level="warning"
    )

    APPLY_PATCH = ToolDefinition(
        name="apply_patch",
        category=ToolCategory.FILE_WRITE,
        description="Applique un patch (unified diff) sur un fichier de manière atomique et robuste",
        parameters={
            "file_path": {"type": "string", "required": True, "description": "Fichier cible à patcher (ex: 'src/app.py')"},
            "patch": {"type": "string", "required": True, "description": "Patch au format unified diff (contient des hunks @@ ... @@)"}
        },
        example={
            "file_path": "src/app.py",
            "patch": "@@ -1,1 +1,1 @@\n-print('hi')\n+print('hello')"
        },
        security_level="dangerous"
    )

    # ========================================
    # OUTILS SYSTÈME ET TERMINAL
    # ========================================

    BASH = ToolDefinition(
        name="bash",
        category=ToolCategory.SYSTEM,
        description="Exécute une commande dans le terminal (comme 'npm install', 'python script.py', 'git status', etc.)",
        parameters={
            "command_line": {"type": "string", "required": True, "description": "Commande à exécuter (exemple: 'npm run dev', 'pip install requests')"},
            "cwd": {"type": "string", "required": True, "description": "Dossier où exécuter la commande"},
            "background": {"type": "boolean", "required": False, "description": "Exécuter en arrière-plan (true) pour les commandes longues"},
            "safe_to_auto_run": {"type": "boolean", "required": False, "description": "Peut s'exécuter automatiquement (true) ou demander confirmation (false)"},
            "wait_ms_before_async": {"type": "number", "required": False, "description": "Temps d'attente en millisecondes avant mode asynchrone"}
        },
        example={
            "command_line": "npm install",
            "cwd": ".",
            "safe_to_auto_run": False
        },
        security_level="dangerous"
    )

    COMMAND_STATUS = ToolDefinition(
        name="command_status",
        category=ToolCategory.SYSTEM,
        description="Vérifie l'état d'une commande qui s'exécute en arrière-plan",
        parameters={
            "command_id": {"type": "string", "required": True, "description": "ID de la commande en cours"},
            "output_character_count": {"type": "number", "required": True, "description": "Nombre de caractères de sortie à récupérer"},
            "wait_duration_seconds": {"type": "number", "required": False, "description": "Temps d'attente maximum en secondes"}
        },
        example={
            "command_id": "cmd_123456",
            "output_character_count": 1000,
            "wait_duration_seconds": 5
        },
        security_level="safe"
    )

    RUN_COMMAND = ToolDefinition(
        name="run_command",
        category=ToolCategory.SYSTEM,
        description="Exécute une commande système (wrapper de bash avec paramètres style Cascade).",
        parameters={
            "CommandLine": {"type": "string", "required": True, "description": "Commande à exécuter"},
            "Cwd": {"type": "string", "required": False, "description": "Répertoire de travail (relatif au workspace)"},
            "Blocking": {"type": "boolean", "required": False, "description": "true = attendre la fin, false = exécution async"},
            "SafeToAutoRun": {"type": "boolean", "required": False, "description": "Indication de sécurité (la policy finale dépend du setting toolExecutionMode)"},
            "WaitMsBeforeAsync": {"type": "number", "required": False, "description": "Compatibilité (non utilisé actuellement côté extension)"}
        },
        example={
            "CommandLine": "npm run dev",
            "Cwd": ".",
            "Blocking": False,
            "SafeToAutoRun": False
        },
        security_level="dangerous"
    )

    READ_TERMINAL = ToolDefinition(
        name="read_terminal",
        category=ToolCategory.SYSTEM,
        description="Lit la sortie d'une commande lancée via bash/run_command. Limitation: ne lit pas un terminal VS Code arbitraire.",
        parameters={
            "Name": {"type": "string", "required": False, "description": "Nom/filtre (best-effort, match dans commandLine)"},
            "ProcessID": {"type": "string", "required": False, "description": "ID retourné par bash/run_command (command_id)"},
            "OutputCharacterCount": {"type": "number", "required": False, "description": "Nombre de caractères à retourner (défaut: 4000)"}
        },
        example={
            "ProcessID": "cmd_123456",
            "OutputCharacterCount": 2000
        },
        security_level="safe"
    )


    # ========================================
    # OUTILS WEB ET RÉSEAU
    # ========================================

    BROWSER_PREVIEW = ToolDefinition(
        name="browser_preview",
        category=ToolCategory.WEB,
        description="Ouvre une URL dans le navigateur de l'utilisateur (utile pour prévisualiser un serveur local ou une page web)",
        parameters={
            "url": {"type": "string", "required": True, "description": "URL à ouvrir (http/https), ex: 'http://localhost:3000'"},
            "name": {"type": "string", "required": False, "description": "Nom court (optionnel) pour décrire la preview"},
        },
        example={
            "url": "http://localhost:3000",
            "name": "Dev Server"
        },
        security_level="warning"
    )

    MCP_FETCH = ToolDefinition(
        name="mcp0_fetch",
        category=ToolCategory.WEB,
        description="Télécharge le contenu d'une page web (documentation, article, etc.)",
        parameters={
            "url": {"type": "string", "required": True, "description": "Adresse de la page à récupérer (exemple: 'https://docs.python.org/3/')"},
            "max_length": {"type": "number", "required": False, "description": "Taille maximale du contenu à récupérer"},
            "raw": {"type": "boolean", "required": False, "description": "Récupérer le HTML brut (true) ou le texte simplifié (false)"},
            "start_index": {"type": "number", "required": False, "description": "Commencer à partir de quel caractère"}
        },
        example={
            "url": "https://numpy.org/doc/stable/",
            "max_length": 10000,
            "raw": False
        },
        security_level="safe"
    )

    SEARCH_WEB = ToolDefinition(
        name="search_web",
        category=ToolCategory.WEB,
        description="Recherche des informations sur internet (comme utiliser Google)",
        parameters={
            "query": {"type": "string", "required": True, "description": "Ce que tu veux rechercher (exemple: 'comment créer une API REST en Python')"},
            "domain": {"type": "string", "required": False, "description": "Chercher uniquement sur un site spécifique (exemple: 'stackoverflow.com')"}
        },
        example={
            "query": "FastAPI tutorial débutant",
            "domain": "fastapi.tiangolo.com"
        },
        security_level="safe"
    )

    # ========================================
    # OUTILS DE GESTION DE MÉMOIRE
    # ========================================

    CREATE_MEMORY = ToolDefinition(
        name="create_memory",
        category=ToolCategory.MEMORY,
        description="Sauvegarde des informations importantes pour s'en souvenir plus tard (architecture du projet, décisions techniques, etc.)",
        parameters={
            "action": {"type": "string", "required": True, "enum": ["create", "update", "delete"], "description": "Action: créer une nouvelle mémoire, mettre à jour, ou supprimer"},
            "title": {"type": "string", "required": True, "description": "Titre court de la mémoire (exemple: 'Architecture du projet')"},
            "content": {"type": "string", "required": True, "description": "Contenu détaillé à sauvegarder"},
            "corpus_names": {"type": "array", "required": True, "items": {"type": "string"}, "description": "Projets concernés par cette mémoire"},
            "tags": {"type": "array", "required": True, "items": {"type": "string"}, "description": "Mots-clés pour retrouver facilement (exemple: ['react', 'typescript', 'api'])"},
            "user_triggered": {"type": "boolean", "required": True, "description": "Est-ce que l'utilisateur a demandé de sauvegarder ça explicitement?"},
            "id": {"type": "string", "required": False, "description": "ID de la mémoire (nécessaire pour update ou delete)"}
        },
        example={
            "action": "create",
            "title": "Structure des dossiers",
            "content": "Le projet suit une architecture MVC. Les routes sont dans /routes, les contrôleurs dans /controllers, et les modèles dans /models.",
            "corpus_names": ["mon-projet-api"],
            "tags": ["architecture", "structure"],
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
        description="Crée ou affiche une liste de tâches à faire (todo list)",
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
                "description": "Liste des tâches avec leur statut"
            }
        },
        example={
            "todos": [
                {
                    "id": "1",
                    "content": "Créer la page de login",
                    "status": "pending",
                    "priority": "high"
                },
                {
                    "id": "2",
                    "content": "Ajouter les tests",
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
            cls.APPLY_PATCH,
            # Système
            cls.BASH,
            cls.COMMAND_STATUS,
            cls.RUN_COMMAND,
            cls.READ_TERMINAL,
            # Web
            cls.MCP_FETCH,
            cls.SEARCH_WEB,
            cls.BROWSER_PREVIEW,
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
            ""
        ]

        # Grouper par catégorie
        categories = {
            ToolCategory.FILE_READ: "📖 LECTURE DE FICHIERS",
            ToolCategory.FILE_WRITE: "✏️ MODIFICATION DE FICHIERS",
            ToolCategory.FILE_SEARCH: "🔍 RECHERCHE DE FICHIERS",
            ToolCategory.SYSTEM: "🖥️ COMMANDES SYSTÈME",
            ToolCategory.WEB: "🌐 INTERNET ET WEB",
            ToolCategory.MEMORY: "🧠 MÉMOIRE ET CONTEXTE",
            ToolCategory.TASK: "📋 GESTION DE TÂCHES",
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
                doc_lines.append(f"{tool.description}")
                doc_lines.append("")

                # Paramètres
                doc_lines.append("**Paramètres:**")
                for param_name, param_spec in tool.parameters.items():
                    required = param_spec.get("required", False)
                    param_type = param_spec.get("type", "string")
                    param_desc = param_spec.get("description", "")
                    required_mark = " ✓" if required else " (optionnel)"
                    doc_lines.append(f"  • `{param_name}` ({param_type}){required_mark}")
                    doc_lines.append(f"    → {param_desc}")

                doc_lines.append("")

                # Exemple pratique
                import json
                doc_lines.append("**Exemple d'utilisation:**")
                doc_lines.append("```")
                example_request = json.dumps(tool.example, ensure_ascii=False)
                doc_lines.append(f"[INTELLITECH_TOOL: {tool.name}, {example_request}]")
                doc_lines.append("```")
                doc_lines.append("")

        # Instructions d'utilisation simplifiées
        doc_lines.append("")
        doc_lines.append("=" * 80)
        doc_lines.append("📝 COMMENT UTILISER CES OUTILS")
        doc_lines.append("=" * 80)
        doc_lines.append("")
        doc_lines.append("1️⃣ Quand l'utilisateur demande quelque chose qui nécessite un outil:")
        doc_lines.append("   → Inclus [INTELLITECH_TOOL: nom_outil, {paramètres}] dans ta réponse")
        doc_lines.append("")
        doc_lines.append("2️⃣ Format JSON strict:")
        doc_lines.append("   → Les paramètres doivent être en JSON valide")
        doc_lines.append("   → Exemple: [INTELLITECH_TOOL: read_file, {\"file_path\": \"src/app.py\"}]")
        doc_lines.append("")
        doc_lines.append("3️⃣ Un seul outil à la fois:")
        doc_lines.append("   → Chaque demande d'outil est indépendante")
        doc_lines.append("   → Attends les résultats avant de demander un autre outil")
        doc_lines.append("")
        doc_lines.append("4️⃣ Gestion de la sécurité:")
        doc_lines.append("   → ✅ Safe: Exécution automatique")
        doc_lines.append("   → ⚠️ Warning: Exécution automatique (par défaut), sauf si l'utilisateur a configuré une policy plus stricte")
        doc_lines.append("   → 🔴 Dangerous: Demande de confirmation (par défaut), sauf si mode 'auto_run'")
        doc_lines.append("")

        return "\n".join(doc_lines)