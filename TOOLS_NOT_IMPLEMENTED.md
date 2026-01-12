# Outils disponibles (Cascade) non implémentés dans `app/services/intellitech_tools_registry.py`

Ce document liste les outils **à la disposition de l’assistant dans l’environnement Cascade** qui ne sont **pas** exposés via le registry `IntelitechToolsRegistry`.

> Remarque: ton registry actuel correspond aux outils exécutables par **l’extension VS Code** (via `IntelitechToolExecutor`). Les outils ci-dessous sont disponibles côté assistant (IDE) mais ne sont pas encore “branchés” dans le protocole `[INTELLITECH_TOOL: ...]` / exécution locale.

## 1) Outils de modification de fichiers (patch/diff)

- `apply_patch`
  - **But**: appliquer un patch multi-hunks (diff) de manière robuste.
  - **Pourquoi manquant**: l’extension exécute aujourd’hui `edit` / `multi_edit` / `write_to_file` uniquement.

## 2) Outils de navigation / preview web

- `browser_preview`
  - **But**: ouvrir une preview interactive d’un serveur local.

## 3) Outils de recherche “Fast Context”

- `code_search`
  - **But**: exploration multi-fichiers assistée (sous-agent) pour cartographier une codebase.

## 4) Outils “lecture web” orientés documents

- `read_url_content`
  - **But**: lire/extraire le contenu d’une URL web.
- `view_content_chunk`
  - **But**: afficher un chunk d’un document déjà lu via `read_url_content`.

> Note: tu as déjà `mcp0_fetch` + `search_web` dans le registry, mais pas ces deux outils orientés “documents/chunks”.

## 5) Outils “ressources” MCP

- `list_resources`
  - **But**: lister les ressources disponibles d’un serveur MCP.
- `read_resource`
  - **But**: lire le contenu d’une ressource MCP.

## 6) Outils terminal (proposition/exécution)

- `run_command`
  - **But**: proposer/exécuter une commande sur la machine (dans Cascade).
  - **Différence**: ton registry expose `bash` (exécution locale via extension) mais pas `run_command` (flow d’approbation côté assistant).
- `read_terminal`
  - **But**: lire la sortie d’un terminal par nom/PID.

## 7) Déploiement web

- `read_deployment_config`
  - **But**: analyser une config de déploiement (pré-check).
- `deploy_web_app`
  - **But**: déployer une web app.
- `check_deploy_status`
  - **But**: vérifier l’état d’un déploiement.

## 8) Outils Netlify (MCP)

- `mcp1_netlify-coding-rules`
- `mcp1_netlify-deploy-services-reader`
- `mcp1_netlify-deploy-services-updater`
- `mcp1_netlify-extension-services-reader`
- `mcp1_netlify-extension-services-updater`
- `mcp1_netlify-project-services-reader`
- `mcp1_netlify-project-services-updater`
- `mcp1_netlify-team-services-reader`
- `mcp1_netlify-user-services-reader`

## 9) Trajectoires (recherche conversation)

- `trajectory_search`
  - **But**: rechercher dans une conversation/trajectoire par ID.

---

## Outils déjà présents dans ton registry (pour contrôle)

Tu exposes déjà notamment:
- `read_file`, `read_notebook`, `list_dir`, `find_by_name`, `grep_search`
- `edit`, `multi_edit`, `edit_notebook`, `write_to_file`
- `bash`, `command_status`
- `mcp0_fetch`, `search_web`
- `create_memory`, `todo_list`

---

## Prochaine étape (si tu veux)

Dis-moi quels outils tu veux réellement **supporter via l’extension** (ex: `apply_patch` est le plus utile), et je te propose:
- la spec JSON (params)
- l’implémentation dans `IntelitechToolExecutor.ts`
- la déclaration correspondante dans `IntelitechToolsRegistry`
