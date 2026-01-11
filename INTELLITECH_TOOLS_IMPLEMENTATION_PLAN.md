# 📋 Plan d'Implémentation - Outils Intelitech pour l'IA

## 🔍 Analyse de la Situation

### Architecture Actuelle

```
┌─────────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Extension VS Code  │ ──────> │  Flask Backend   │ ──────> │  Gemini API     │
│   (Intelitech)      │ <────── │  (/api/defai/    │ <────── │  (IA Backend)   │
│                     │         │   chat)          │         │                 │
└─────────────────────┘         └──────────────────┘         └─────────────────┘
```

**Flux actuel:**
1. L'extension VS Code envoie une requête POST à `/api/defai/chat`
2. Le serveur Flask prépare le contexte (code sélectionné, historique, etc.)
3. Le serveur appelle Gemini via `GeminiIntegration.generate_response()`
4. Gemini peut générer des `[NEED_DATA: type, description]` pour les données de la plateforme
5. Ces demandes sont exécutées via `AIOrchestrator.execute_request()`
6. La réponse finale est renvoyée à l'extension

**Point important:** Le système gère déjà un mécanisme similaire pour les données de la plateforme (`[NEED_DATA: ...]`).

### Nouveaux Besoins

Les outils définis dans `fonc.md` doivent être exécutés **localement sur la machine de l'utilisateur**, pas sur le serveur Flask, car:
- Le serveur n'a pas accès au système de fichiers local
- Les commandes système doivent s'exécuter dans l'environnement de l'utilisateur
- La sécurité impose que les modifications de fichiers soient sous contrôle de l'utilisateur

### Solution Proposée

**Architecture avec outils locaux:**

```
┌─────────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Extension VS Code  │         │  Flask Backend   │         │  Gemini API     │
│   (Intelitech)      │         │                  │         │                 │
│                     │         │                  │         │                 │
│  - Parse [TOOL:...] │         │  - Parse [TOOL]  │         │  - Génère       │
│  - Exécute outils   │         │  - Inclut docs   │         │    [TOOL:...]   │
│  - Retourne résultats│        │    dans prompt   │         │    dans réponse │
└─────────────────────┘         └──────────────────┘         └─────────────────┘
```

**Nouveau flux:**
1. L'extension envoie la requête initiale (peut inclure des résultats d'outils précédents)
2. Le serveur inclut la documentation des outils dans le prompt système
3. Gemini génère `[INTELLITECH_TOOL: tool_name, {params}]` si nécessaire
4. Le serveur parse ces demandes et les inclut dans la réponse JSON
5. L'extension exécute les outils localement
6. L'extension renvoie les résultats dans la prochaine requête
7. Le serveur inclut ces résultats dans le contexte pour la prochaine réponse

---

## 📐 Plan d'Implémentation

### Phase 1: Définition et Documentation des Outils ✅

**Fichier créé:** `app/services/intellitech_tools_registry.py`

**Contenu:**
- ✅ Définition de tous les outils avec leurs paramètres
- ✅ Documentation structurée pour le prompt système
- ✅ Classification par catégorie et niveau de sécurité

**Outils définis:**
- **Lecture:** `read_file`, `read_notebook`, `list_dir`, `find_by_name`, `grep_search`
- **Édition:** `edit`, `multi_edit`, `edit_notebook`, `write_to_file`
- **Système:** `bash`, `command_status`
- **Web:** `mcp0_fetch`, `search_web`
- **Mémoire:** `create_memory`
- **Tâches:** `todo_list`

---

### Phase 2: Prompt Système Dédié pour l'Extension ✅

**Fichier créé:** `app/services/intellitech_prompt.py`

**Raison:** Séparation du prompt système pour optimiser les tokens envoyés à Gemini et créer un prompt spécialisé pour le contexte de développement.

**Contenu:**
- ✅ Prompt système optimisé et concis pour l'extension
- ✅ Documentation complète des outils disponibles
- ✅ Format de réponse attendu avec exemples
- ✅ Règles de sécurité essentielles
- ✅ Méthode `build_complete_prompt()` pour construire le prompt final
- ✅ Gestion du contexte (code, résultats d'outils, historique)

**Structure:**
```python
class IntelitechPromptBuilder:
    @staticmethod
    def build_system_prompt() -> str:
        # Prompt système de base
    
    @staticmethod
    def build_complete_prompt(user_message, code_context, tool_results, conversation_history) -> str:
        # Prompt complet avec contexte
```

**Avantages:**
- Prompt plus court (économise des tokens)
- Spécialisé pour le contexte de développement
- Facilite la maintenance et l'évolution
- Pas d'impact sur le prompt système principal de la plateforme

---

### Phase 3: Parser des Demandes d'Outils dans Gemini ✅

**Fichier modifié:** `app/services/gemini_integration.py`

**Actions réalisées:**
1. ✅ Ajout de la méthode `_parse_intellitech_tool_requests()` similaire à `_parse_data_requests()`
2. ✅ Détection du pattern `[INTELLITECH_TOOL: tool_name, {params}]` dans la réponse
3. ✅ Validation que l'outil existe dans le registry
4. ✅ Parsing et validation des paramètres JSON
5. ✅ Intégration dans `_process_response()` pour retourner les demandes d'outils
6. ✅ Suppression des demandes d'outils du texte nettoyé dans `_clean_response_text()`

**Pattern regex utilisé:**
```python
r"\[INTELLITECH_TOOL:\s*([^,]+),\s*(\{[^\}]*(?:\{[^\}]*\}[^\}]*)*\})\s*\]"
```
*Note: Pattern amélioré pour gérer les JSON imbriqués*

**Format de retour:**
```python
{
    "success": True,
    "response": "...",
    "intellitech_tool_requests": [
        {
            "tool_name": "read_file",
            "parameters": {"file_path": "...", "limit": 50}
        }
    ]
}
```

**Fonctionnalités:**
- Validation des outils via `IntelitechToolsRegistry.get_tool_by_name()`
- Parsing sécurisé des paramètres JSON avec gestion d'erreurs
- Validation des paramètres obligatoires (avec warnings si manquants)
- Logging détaillé pour le débogage
- Support des JSON imbriqués dans les paramètres

---

### Phase 4: Intégration dans l'Endpoint API ✅

**Fichier modifié:** `app/routes/api.py` (fonction `defai_chat`)

**Actions réalisées:**
1. ✅ Détection si la requête provient de l'extension VS Code (`source: "vscode_extension"`)
2. ✅ Utilisation de `IntelitechPromptBuilder` pour les requêtes de l'extension
3. ✅ Construction du prompt avec `build_complete_prompt()` incluant:
   - Le contexte de code (`code_context`)
   - Les résultats d'outils précédents (`tool_results`)
   - L'historique de conversation
4. ✅ Appel direct à `GeminiIntegration.generate_response()` avec `use_system_prompt=False`
5. ✅ Extraction des demandes d'outils de la réponse Gemini
6. ✅ Inclusion des demandes d'outils dans la réponse JSON
7. ✅ Sauvegarde des demandes d'outils dans `extra_data` du message
8. ✅ Rétrocompatibilité avec l'ancien système (si `source != "vscode_extension"`)

**Code implémenté:**
```python
from app.services.intellitech_prompt import IntelitechPromptBuilder

# Dans defai_chat():
if data.get("source") == "vscode_extension":
    # Utiliser le prompt dédié
    full_prompt = IntelitechPromptBuilder.build_complete_prompt(
        user_message=message,
        code_context=code_context_dict,
        tool_results=data.get("tool_results", []),
        conversation_history=messages_history
    )
    
    # Appeler Gemini avec use_system_prompt=False (déjà dans le prompt)
    gemini_response = gemini.generate_response(
        prompt=full_prompt,
        context=None,  # Déjà inclus dans le prompt
        use_system_prompt=False  # Prompt système déjà intégré
    )
```

**Structure de la requête (avec résultats d'outils):**
```json
{
    "message": "Analyse ce fichier",
    "source": "vscode_extension",
    "code_context": {
        "file_path": "src/main.ts",
        "language": "TypeScript",
        "selected_code": "function test() {...}"
    },
    "tool_results": [
        {
            "tool_name": "read_file",
            "success": true,
            "result": "...",
            "request_id": "req_123"
        }
    ],
    "conversation_id": 456
}
```

**Structure de la réponse (sans streaming):**
```json
{
    "success": true,
    "reply": "Réponse de l'IA...",
    "tool_requests": [
        {
            "tool_name": "read_file",
            "parameters": {"file_path": "...", "limit": 50},
            "request_id": "req_456"
        }
    ],
    "conversation_id": 456,
    "message_id": 789
}
```

**Structure de la réponse (avec streaming - SSE):**
```
event: chunk
data: {"type": "chunk", "content": "Voici l'analyse"}

event: chunk
data: {"type": "chunk", "content": " du fichier..."}

event: tool_request
data: {"type": "tool_request", "tool_name": "read_file", "parameters": {...}, "request_id": "req_456"}

event: done
data: {"type": "done", "conversation_id": 456, "message_id": 789}
```

---

### Phase 5: Gestion du Système de Référencement `@`

**Fichier à créer:** `app/services/intellitech_reference_parser.py`

**Fonctionnalité:** Parser les références `@fichier`, `@dossier/`, `@*.ext`, `@function:nom`

**Actions:**
1. Détecter les patterns `@` dans le message utilisateur
2. Résoudre les chemins relatifs en chemins absolus (nécessite workspace root de l'extension)
3. Générer automatiquement des demandes d'outils `read_file`, `list_dir`, `grep_search`
4. Pré-exécuter ces outils avant d'envoyer à Gemini (optionnel, ou laisser Gemini les demander)

**Exemple:**
```
Message: "Analyse @src/main.ts et la fonction @function:initializeApp"
→ Génère: [INTELLITECH_TOOL: read_file, {"file_path": "src/main.ts"}]
→ Génère: [INTELLITECH_TOOL: grep_search, {"query": "function initializeApp", ...}]
```

---

### Phase 6: Streaming des Réponses et Mise à Jour de l'Interface

**Phase 6a: Implémentation du Streaming (Backend)**

**Fichier à modifier:** `app/services/gemini_integration.py`

**Actions:**
1. Ajouter une méthode `generate_response_stream()` pour le streaming
2. Utiliser l'endpoint streaming de Gemini API (`generateContent` avec `stream=True`)
3. Parser les chunks de réponse au fur et à mesure
4. Détecter les demandes d'outils dans les chunks
5. Yielder les chunks pour Flask StreamingResponse

**Fichier à modifier:** `app/routes/api.py`

**Actions:**
1. Créer une nouvelle route `/api/defai/chat/stream` pour le streaming
2. Utiliser `Response(stream_with_context(...), mimetype='text/event-stream')`
3. Envoyer les chunks au format Server-Sent Events (SSE)
4. Gérer les demandes d'outils dans le stream

**Format SSE:**
```
data: {"type": "chunk", "content": "texte..."}
data: {"type": "tool_request", "tool_name": "...", "parameters": {...}}
data: {"type": "done"}
```

**Phase 6b: Modifications dans l'Extension VS Code (TypeScript)**

**Fichiers à modifier dans `intellitech/src/`:**

1. **Service de communication:**
   - Ajouter support SSE pour le streaming
   - Parser les événements SSE
   - Émettre des événements pour chaque chunk reçu

2. **Gestionnaire d'outils:**
   - Créer `intellitechToolExecutor.ts` pour exécuter les outils localement
   - Implémenter chaque outil (read_file, edit, bash, etc.)
   - Gestion des erreurs et validation des paramètres

3. **Interface utilisateur (DefaiChatProvider.ts):**
   - Afficher les réponses en streaming (texte qui apparaît progressivement)
   - Afficher les demandes d'outils avec boutons d'action
   - Demander confirmation pour les outils dangereux (modal/dialog)
   - Afficher les résultats d'outils exécutés
   - Gérer l'état de chargement et les erreurs

4. **Envoi des résultats:**
   - Inclure les résultats d'outils dans les requêtes suivantes
   - Gérer le cycle: demande → outil → résultat → réponse finale

**Structure TypeScript suggérée:**

```typescript
// intellitech/src/services/intellitechToolExecutor.ts
interface ToolRequest {
    tool_name: string;
    parameters: any;
    request_id: string;
}

interface ToolResult {
    tool_name: string;
    success: boolean;
    result: any;
    error?: string;
    request_id: string;
}

class IntelitechToolExecutor {
    async executeTool(request: ToolRequest): Promise<ToolResult> {
        // Implémentation locale de chaque outil
        switch (request.tool_name) {
            case 'read_file':
                return this.executeReadFile(request.parameters);
            case 'edit':
                return this.executeEdit(request.parameters);
            // etc.
        }
    }
}
```

---

## 🔐 Considérations de Sécurité

### 1. Validation des Chemins
- ✅ Vérifier que les chemins sont dans le workspace
- ✅ Empêcher l'accès aux fichiers système (`C:\\Windows`, `/etc`, etc.)
- ✅ Respecter `.gitignore`, `.defignore`  et autres fichiers d'exclusion

### 2. Confirmation Utilisateur
- ⚠️ **Obligatoire** pour les outils avec `security_level: "dangerous"` (bash, edit, write_to_file)
- ⚠️ **Recommandé** pour `security_level: "warning"` (multi_edit)
- ✅ **Automatique** pour `security_level: "safe"` (read_file, list_dir)

### 3. Sanitization
- ✅ Valider les paramètres selon les schémas définis
- ✅ Limiter la taille des fichiers lus (ex: 1MB max)
- ✅ Timeout pour les commandes système (ex: 30 secondes)
- ✅ Sandboxing pour les commandes bash (recommandé)

### 4. Logging
- ✅ Logger toutes les exécutions d'outils
- ✅ Logger les erreurs et échecs
- ✅ Stocker un historique pour audit

---

## 📊 Ordre de Priorité d'Implémentation

### Priorité 1 (Essentiel) 🔴
1. ✅ **Phase 1:** Définition des outils (FAIT)
2. ✅ **Phase 2:** Prompt système dédié (FAIT)
3. **Phase 3:** Parser des demandes dans Gemini
4. **Phase 4:** Intégration dans l'endpoint API (sans streaming)
5. **Phase 6a:** Implémentation du streaming backend
6. **Phase 6b (partie 1):** Interface streaming dans l'extension

### Priorité 2 (Important) 🟡
7. **Phase 6b (partie 2):** Implémentation basique des outils dans l'extension
   - Lecture de fichiers (`read_file`, `list_dir`)
   - Recherche (`find_by_name`, `grep_search`)
8. **Sécurité:** Validation des chemins et confirmations
9. **Phase 6b (partie 3):** Gestion des demandes d'outils dans l'interface
   - Affichage des demandes
   - Exécution automatique des outils "safe"
   - Confirmation pour outils "warning" et "dangerous"

### Priorité 3 (Amélioration) 🟢
10. **Phase 5:** Système de référencement `@`
11. **Phase 6b (partie 4):** Outils d'édition (`edit`, `write_to_file`)
12. **Phase 6b (partie 5):** Outils système (`bash`, `command_status`)
13. **Phase 6b (partie 6):** Outils avancés (mémoire, tâches, web)
14. **Optimisations:** Cache des résultats d'outils, debouncing, etc.

---

## 🧪 Tests à Prévoir

### Tests Backend (Python)
- ✅ Parser des demandes d'outils dans les réponses Gemini
- ✅ Validation des schémas d'outils
- ✅ Génération de la documentation des outils
- ✅ Gestion des erreurs et cas limites

### Tests Extension (TypeScript)
- ✅ Exécution de chaque outil individuellement
- ✅ Validation des paramètres
- ✅ Gestion des erreurs
- ✅ Confirmation utilisateur pour outils dangereux
- ✅ Intégration avec le système de communication API

### Tests d'Intégration
- ✅ Flux complet: demande → outil → résultat → réponse
- ✅ Gestion de plusieurs outils dans une même réponse
- ✅ Gestion des erreurs d'exécution d'outils
- ✅ Performance avec gros fichiers

---

## 📝 Notes d'Implémentation

### Format JSON Strict
Les paramètres des outils doivent être en JSON valide. Utiliser `json.loads()` avec gestion d'erreurs.

### Gestion des Erreurs
- Si un outil échoue, retourner `{"success": false, "error": "..."}` dans `tool_results`
- L'IA peut alors adapter sa réponse en fonction des erreurs

### Performance
- Limiter la taille des réponses d'outils (ex: 10KB par résultat)
- Pour les gros fichiers, utiliser `limit` et `offset` dans `read_file`
- Chunking pour les résultats volumineux

### Compatibilité
- S'assurer que le format fonctionne avec les versions futures de Gemini
- Prévoir une versioning des outils si nécessaire
- Documentation claire pour les développeurs de l'extension

---

## ✅ Checklist de Vérification

- [x] Phase 1: Registry des outils créé
- [x] Phase 2: Prompt système dédié créé (intellitech_prompt.py)
- [x] Phase 3: Parser dans gemini_integration.py
- [x] Phase 4: Intégration dans api.py (endpoint standard)
- [ ] Phase 6a: Streaming backend (endpoint /stream)
- [ ] Phase 6b (partie 1): Interface streaming dans l'extension
- [ ] Phase 6b (partie 2): Outils de base (read_file, list_dir, grep)
- [ ] Phase 6b (partie 3): Gestion des demandes d'outils dans l'UI
- [ ] Phase 5: Parser de références @ (optionnel)
- [ ] Phase 6b (partie 4+): Outils avancés (edit, bash, etc.)
- [ ] Tests backend (parser, streaming)
- [ ] Tests extension (outils, streaming, UI)
- [ ] Tests d'intégration (flux complet)
- [ ] Documentation utilisateur
- [ ] Documentation développeur

---

## 🎯 Résultat Final Attendu

L'utilisateur pourra:
1. Demander à l'IA d'analyser des fichiers de son projet
2. Demander à l'IA de modifier du code
3. Demander à l'IA d'exécuter des commandes (avec confirmation)
4. Utiliser des références `@fichier` pour pointer vers des fichiers
5. Bénéficier d'une assistance intelligente directement dans VS Code

L'IA pourra:
1. Demander l'exécution d'outils via `[INTELLITECH_TOOL: ...]`
2. Recevoir les résultats et les intégrer dans ses réponses
3. Enchaîner plusieurs outils si nécessaire
4. Adapter ses réponses selon les résultats des outils
