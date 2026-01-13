/**
 * defAI Chat Interface Script
 * Handles UI interactions, API communication, and Markdown rendering.
 */

const CONFIG = {
    csrfToken: document.querySelector('meta[name="csrf-token"]')?.content,
    endpoints: {
        // API endpoints exposed by ai_assistant_bp (url_prefix="/api/ai")
        chat: '/api/ai/chat',
        history: '/api/ai/conversations',
        new: '/api/ai/conversations'
    },
    selectors: {
        messages: '#messages',
        form: '#chatForm',
        input: '#userInput',
        sidebar: '#sidebar',
        sidebarToggle: '#sidebarToggle',
        sidebarOverlay: '#sidebarOverlay',
        themeToggle: '#themeToggle',
        welcome: '#welcomeState',
        attachBtn: '#attachBtn',
        fileInput: '#fileInput',
        voiceBtn: '#voiceInputBtn',
        conversationList: '#conversationList',
        toastContainer: '#toast-container',
        dynamicLoaders: '#dynamicLoaders'
    }
};

const State = {
    isTyping: false,
    currentConversationId: null,
    theme: localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'),
    recognition: null,
    isRecording: false,
    isSystemTheme: !localStorage.getItem('theme'),
    lastUserMessage: '',
    convPagination: { page: 1, hasMore: true, isLoading: false }
};

const UI = {
    elements: {},

    setupToolCallsVisibility() {
        const btn = document.getElementById('toolCallsToggle');
        const apply = (show) => {
            const shouldShow = show === true;
            document.documentElement.classList.toggle('hide-intellitech-tools', !shouldShow);
            try {
                localStorage.setItem('showIntellitechTools', shouldShow ? '1' : '0');
            } catch {
                // ignore
            }
        };

        let show = true;
        try {
            const stored = localStorage.getItem('showIntellitechTools');
            if (stored === '0') show = false;
        } catch {
            // ignore
        }

        apply(show);

        if (btn) {
            btn.addEventListener('click', () => {
                const isHidden = document.documentElement.classList.contains('hide-intellitech-tools');
                apply(isHidden);
            });
        }
    },

    showFetchLoader(label) {
        const container = document.getElementById('dynamicLoaders');
        if (!container) return;

        let loader = document.getElementById('fetchLoader');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'fetchLoader';
            loader.className = 'loader-container fetch-loader';
            container.appendChild(loader);
        }

        loader.innerHTML = `
            <i class="fas fa-spinner fa-spin loader-icon"></i>
            <span class="text-sm font-medium">${this.escapeHtml(label || 'Chargement...')}</span>
        `;
    },

    hideFetchLoader() {
        const loader = document.getElementById('fetchLoader');
        if (loader) {
            loader.classList.add('fade-out');
            setTimeout(() => loader.remove(), 300);
        }
    },

    init() {
        // Initialize elements
        for (const [key, selector] of Object.entries(CONFIG.selectors)) {
            this.elements[key] = document.querySelector(selector);
        }

        // Initialize Sidebar Accessibility
        if (this.elements.sidebar && this.elements.sidebar.classList.contains('-translate-x-full')) {
            this.elements.sidebar.setAttribute('inert', '');
            this.elements.sidebar.setAttribute('aria-hidden', 'true');
        }

        this.setupTheme();
        this.setupMarkdown();
        this.setupEventListeners();
        this.setupSpeechRecognition();
        this.adjustTextareaHeight();

        // Check for existing conversation
        const appContainer = document.getElementById('app-container');
        if (appContainer && appContainer.dataset.conversationId) {
            State.currentConversationId = parseInt(appContainer.dataset.conversationId);
            this.loadConversationHistory(State.currentConversationId);
        }

        this.loadConversations();

        this.setupToolCallsVisibility();

        // Scroll listener for messages (existing)
        if (this.elements.messages) {
            this.elements.messages.addEventListener('scroll', () => {
                if (this.elements.messages.scrollTop === 0) {
                    this.loadMoreMessages();
                }
            });
        }

        // Scroll listener for conversations (infinite scroll)
        if (this.elements.conversationList) {
            this.elements.conversationList.addEventListener('scroll', () => {
                const { scrollTop, scrollHeight, clientHeight } = this.elements.conversationList;
                if (scrollTop + clientHeight >= scrollHeight - 30) { // Near bottom
                    this.loadMoreConversations();
                }
            });
        }

        // Handle browser back/forward
        window.addEventListener('popstate', (event) => {
            if (event.state && event.state.conversationId) {
                this.setActiveConversation(event.state.conversationId, false);
            } else {
                // Handle initial state or root
                const pathParts = window.location.pathname.split('/');
                const linkOrId = pathParts[pathParts.length - 1];
                if (linkOrId && linkOrId !== 'chat') {
                    // Try to match linkOrId to a conversation? 
                    // For now, simpler to just reload or let default behavior if it was a deep link load.
                    // But if we are navigating back to "empty" chat, we might want to clear.
                    if (linkOrId === 'chat') {
                        this.clearActiveConversation();
                    }
                }
            }
        });
    },

    async loadConversations(append = false) {
        if (!append) {
            State.convPagination = { page: 1, hasMore: true, isLoading: false };
        }

        if (State.convPagination.isLoading) return;
        State.convPagination.isLoading = true;

        try {
            this.showFetchLoader('Chargement des conversations...');
            const response = await fetch(`${CONFIG.endpoints.history}?page=${State.convPagination.page}`);
            if (!response.ok) throw new Error('Failed to load conversations');

            const data = await response.json();
            const conversations = data.conversations || [];
            const listEl = this.elements.conversationList;

            if (!listEl) return;

            if (!append) listEl.innerHTML = '';

            if (conversations.length === 0 && !append) {
                listEl.innerHTML = '<div class="text-center py-8 text-gray-400 text-sm italic">Aucune conversation récente</div>';
                State.convPagination.hasMore = false;
                return;
            }

            if (data.pagination) {
                State.convPagination.hasMore = data.pagination.has_next;
            }

            conversations.forEach(conv => {
                const el = document.createElement('div');
                el.className = "relative group mb-1";

                // Style calc
                const isActive = State.currentConversationId === conv.id;
                const baseClass = "block p-3 rounded-xl transition-all duration-200 hover:bg-gray-100 dark:hover:bg-dark-surface group conversation-item flex items-center gap-3";
                const activeClass = "bg-primary-50 dark:bg-primary-900/10 border border-primary-100 dark:border-primary-800";
                const inactiveClass = "border border-transparent";

                const time = new Date(conv.updated_at).toLocaleDateString();
                const url = conv.link ? `/api/ai/chat/${conv.link}` : '/defAI';

                el.innerHTML = `
                    <a href="${url}" class="${baseClass} ${isActive ? activeClass : inactiveClass} flex-1 min-w-0" data-id="${conv.id}" data-link="${conv.link || ''}">
                        <div class="w-8 h-8 rounded-lg bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-400 flex-shrink-0">
                            <i class="fas fa-comments text-xs"></i>
                        </div>
                        <div class="flex-1 min-w-0">
                            <h4 class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors">
                                ${conv.title || 'Nouvelle conversation'}
                            </h4>
                            <p class="text-xs text-gray-500 dark:text-gray-400 truncate">
                                ${conv.last_message || '...'}
                            </p>
                        </div>
                        <div class="text-[10px] text-gray-400 flex-shrink-0 pr-6">
                            ${time}
                        </div>
                    </a>
                    <button class="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all z-10 delete-conv-btn" 
                            title="Supprimer la conversation"
                            onclick="UI.deleteConversation(event, ${conv.id})">
                        <i class="fas fa-trash-alt text-xs"></i>
                    </button>
                `;

                const link = el.querySelector('a');
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.setActiveConversation(conv.id, true, conv.link || conv.id);
                    if (window.innerWidth < 1024) this.toggleSidebar();
                });

                listEl.appendChild(el);
            });

        } catch (error) {
            console.error('Error loading conversations:', error);
            this.showToast('Impossible de charger les conversations', 'error');
        } finally {
            this.hideFetchLoader();
            State.convPagination.isLoading = false;
        }
    },

    async loadMoreConversations() {
        if (!State.convPagination.hasMore || State.convPagination.isLoading) return;
        State.convPagination.page++;
        await this.loadConversations(true);
    },

    async deleteConversation(e, id) {
        e.preventDefault();
        e.stopPropagation();

        if (!confirm('Voulez-vous vraiment supprimer cette conversation ?')) return;

        try {
            const response = await fetch(`/api/ai/conversations/${id}/delete`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': CONFIG.csrfToken
                }
            });

            if (!response.ok) throw new Error('Failed to delete conversation');

            const data = await response.json();
            if (data.success) {
                this.showToast('Conversation supprimée', 'success');

                // If the deleted conversation was the active one, start a new chat
                if (State.currentConversationId === id) {
                    this.clearActiveConversation();
                    window.history.pushState({}, '', '/defAI');
                }

                // Reload list (or remove element)
                this.loadConversations();
            } else {
                this.showToast(data.error || 'Erreur lors de la suppression', 'error');
            }
        } catch (error) {
            console.error('Delete error:', error);
            this.showToast('Erreur serveur lors de la suppression', 'error');
        }
    },

    setActiveConversation(id, pushState = true, linkPart = null) {
        if (State.currentConversationId === id) return;

        State.currentConversationId = id;

        // Update Sidebar UI
        document.querySelectorAll('.conversation-item').forEach(el => {
            const isActive = parseInt(el.dataset.id) === id;
            if (isActive) {
                el.classList.add('bg-primary-50', 'dark:bg-primary-900/10', 'border-primary-100', 'dark:border-primary-800');
                el.classList.remove('border-transparent');
            } else {
                el.classList.remove('bg-primary-50', 'dark:bg-primary-900/10', 'border-primary-100', 'dark:border-primary-800');
                el.classList.add('border-transparent');
            }
        });

        // Load Content
        this.loadConversationHistory(id);

        // Update URL (deep link conversation)
        if (pushState) {
            const url = linkPart ? `/api/ai/chat/${linkPart}` : '/defAI';
            window.history.pushState({ conversationId: id }, '', url);
        }
    },

    clearActiveConversation() {
        State.currentConversationId = null;
        this.elements.messages.innerHTML = '';
        if (this.elements.welcome) this.elements.welcome.style.display = 'flex';
        // Reset sidebar selection
        document.querySelectorAll('.conversation-item').forEach(el => {
            el.classList.remove('bg-primary-50', 'dark:bg-primary-900/10', 'border-primary-100', 'dark:border-primary-800');
            el.classList.add('border-transparent');
        });
    },

    async loadConversationHistory(conversationId) {
        try {
            this.showFetchLoader('Chargement de la conversation...');
            State.pagination = { page: 1, hasMore: true, isLoading: false }; // Reset pagination

            const response = await fetch(`/api/ai/conversations/${conversationId}?page=1`);
            if (!response.ok) throw new Error('Failed to load conversation');

            const data = await response.json();
            const messages = data.messages || [];

            // Update pagination state
            if (data.pagination) {
                State.pagination.page = data.pagination.page;
                State.pagination.hasMore = data.pagination.has_more;
            }

            this.elements.messages.innerHTML = ''; // Clear existing
            this.elements.messages.classList.remove('hidden');

            if (this.elements.welcome) {
                this.elements.welcome.style.display = messages.length ? 'none' : 'flex';
            }

            messages.forEach(msg => {
                const isUser = msg.sender_id === (data.user_id || 0) || msg.message_type === 'user';
                this.elements.messages.appendChild(this.createMessageElement(msg.content, isUser, msg.attachments || []));
            });

            this.scrollToBottom();
            // hljs.highlightAll(); // Removed to prevent double highlighting
        } catch (error) {
            console.error('Error loading history:', error);
            this.showToast('Erreur lors du chargement de la conversation', 'error');
        } finally {
            this.hideFetchLoader();
        }
    },

    async loadMoreMessages() {
        if (!State.currentConversationId || !State.pagination.hasMore || State.pagination.isLoading) return;

        State.pagination.isLoading = true;
        const nextPage = State.pagination.page + 1;
        const currentHeight = this.elements.messages.scrollHeight;

        try {
            this.showFetchLoader('Chargement...');
            const response = await fetch(`/api/ai/conversations/${State.currentConversationId}?page=${nextPage}`);
            if (!response.ok) throw new Error('Failed to load more messages');

            const data = await response.json();
            const messages = data.messages || [];

            if (data.pagination) {
                State.pagination.page = data.pagination.page;
                State.pagination.hasMore = data.pagination.has_more;
            } else {
                State.pagination.hasMore = false;
            }

            // Prepend messages
            messages.reverse().forEach(msg => { // Reverse because we want oldest at top of prepend list? No, API returns chronological.
                // Wait, API returns chronological.
                // If I have [M1, M2] on page 2 (older) and [M3, M4] on page 1 (newer).
                // I want to prepend M1 then M2. 
                // messages is [M1, M2].
                // Prepending M1 then M2 results in M2 M1 M3 M4.
                // Correct order is M1 M2 M3 M4.
                // So I should prepend in reverse order of the list? 
                // No, I should prepend the BLOCK [M1, M2].
                // appendChild adds to bottom.
                // insertBefore adds to top.
                // If I loop messages:
                // Prepend M1: [M1, M3, M4]
                // Prepend M2: [M2, M1, M3, M4] -> WRONG.
                // So I must loop messages in REVERSE to prepend properly, OR create a fragment.
            });

            // Using a fragment is cleaner
            const fragment = document.createDocumentFragment();
            messages.forEach(msg => {
                const isUser = msg.sender_id === (data.user_id || 0) || msg.message_type === 'user';
                fragment.appendChild(this.createMessageElement(msg.content, isUser, msg.attachments || []));
            });
            this.elements.messages.insertBefore(fragment, this.elements.messages.firstChild);

            // hljs.highlightAll(); // Removed


            // Maintain scroll position
            const newHeight = this.elements.messages.scrollHeight;
            this.elements.messages.scrollTop = newHeight - currentHeight;

        } catch (error) {
            console.error('Error loading more messages:', error);
            this.showToast('Impossible de charger plus de messages', 'error');
        } finally {
            this.hideFetchLoader();
            State.pagination.isLoading = false;
        }
    },

    setupTheme() {
        // Appliquer le thème sauvegardé ou la préférence système
        const theme = State.theme;

        if (theme === 'dark' || (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.classList.add('dark');
            document.documentElement.setAttribute('data-theme', 'dark');
            State.theme = 'dark';
        } else {
            document.documentElement.classList.remove('dark');
            document.documentElement.setAttribute('data-theme', 'light');
            State.theme = 'light';
        }

        this.updateThemeToggleIcon();

        // Écouter les changements de thème système si aucun thème n'est forcé
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (!localStorage.getItem('theme')) {
                if (e.matches) {
                    document.documentElement.classList.add('dark');
                    document.documentElement.setAttribute('data-theme', 'dark');
                    State.theme = 'dark';
                } else {
                    document.documentElement.classList.remove('dark');
                    document.documentElement.setAttribute('data-theme', 'light');
                    State.theme = 'light';
                }
                this.updateThemeToggleIcon();
            }
        });
    },

    toggleTheme() {
        if (State.theme === 'dark') {
            State.theme = 'light';
            State.isSystemTheme = false;
            localStorage.setItem('theme', 'light');
            document.documentElement.classList.remove('dark');
            document.documentElement.setAttribute('data-theme', 'light');
        } else if (State.theme === 'light') {
            State.theme = 'dark';
            State.isSystemTheme = false;
            localStorage.setItem('theme', 'dark');
            document.documentElement.classList.add('dark');
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            // If no theme was set, use system preference
            State.isSystemTheme = true;
            localStorage.removeItem('theme');
            if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
                document.documentElement.classList.add('dark');
                document.documentElement.setAttribute('data-theme', 'dark');
            } else {
                document.documentElement.classList.remove('dark');
                document.documentElement.setAttribute('data-theme', 'light');
            }
        }

        // Update UI elements
        this.updateThemeToggleIcon();
    },

    updateThemeToggleIcon() {
        const themeToggle = this.elements.themeToggle;
        if (!themeToggle) return;

        const isDark = document.documentElement.classList.contains('dark');
        const moonIcon = themeToggle.querySelector('.fa-moon');
        const sunIcon = themeToggle.querySelector('.fa-sun');

        if (isDark) {
            moonIcon?.classList.add('hidden');
            sunIcon?.classList.remove('hidden');
        } else {
            sunIcon?.classList.add('hidden');
            moonIcon?.classList.remove('hidden');
        }
    },

    setupMarkdown() {
        // Configuration de marked pour le rendu Markdown
        marked.setOptions({
            highlight: function (code, lang) {
                try {
                    if (lang && hljs.getLanguage(lang)) {
                        return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
                    }
                    return hljs.highlightAuto(code).value;
                } catch (e) {
                    console.warn('Erreur de coloration syntaxique:', e);
                    return code; // Retourne le code non coloré en cas d'erreur
                }
            },
            langPrefix: 'hljs language-',
            breaks: true,
            gfm: true,
            smartLists: true,
            smartypants: true,
            xhtml: true
        });

        // Configuration de DOMPurify pour la sécurité
        if (window.DOMPurify) {
            DOMPurify.setConfig({
                ALLOWED_TAGS: [
                    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'p', 'a', 'ul', 'ol',
                    'li', 'b', 'i', 'strong', 'em', 'strike', 'code', 'hr', 'br', 'div',
                    'table', 'thead', 'tbody', 'tr', 'th', 'td', 'pre', 'span', 'img'
                ],
                ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'target', 'rel'],
                ALLOW_DATA_ATTR: false
            });
        }
    },

    setupSpeechRecognition() {
        // Détection iOS/Safari
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
            (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
        const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);

        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            State.recognition = new SpeechRecognition();
            State.recognition.continuous = false;
            State.recognition.interimResults = false;
            State.recognition.lang = 'fr-FR';

            State.recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                const input = this.elements.input;
                input.value += (input.value ? ' ' : '') + transcript;
                this.adjustTextareaHeight();
                this.stopRecording();
            };

            State.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                this.stopRecording();

                // Message d'erreur spécifique iOS
                if (isIOS && event.error === 'not-allowed') {
                    showToast('Veuillez autoriser l\'accès au microphone dans les réglages Safari.', 'error');
                } else {
                    showToast('Erreur lors de la reconnaissance vocale: ' + event.error, 'error');
                }
            };

            State.recognition.onend = () => {
                this.stopRecording();
            };

            // Stocker l'état iOS pour utilisation dans startRecording
            State.isIOS = isIOS;
            State.isSafari = isSafari;
        } else {
            console.warn('Votre navigateur ne supporte pas la reconnaissance vocale');
            showToast('Votre navigateur ne supporte pas la reconnaissance vocale', 'error');
            if (this.elements.voiceBtn) this.elements.voiceBtn.style.display = 'none';
        }
    },

    toggleRecording() {
        if (!State.recognition) return;

        if (State.isRecording) {
            this.stopRecording();
        } else {
            this.startRecording();
        }
    },

    async startRecording() {
        try {
            // Pour iOS/Safari : vérifier et demander la permission micro avant
            if (State.isIOS || State.isSafari) {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    // Arrêter le stream immédiatement car on va utiliser Speech Recognition
                    stream.getTracks().forEach(track => track.stop());
                } catch (permErr) {
                    console.error('Microphone permission denied:', permErr);
                    showToast('Accès au microphone requis. Veuillez autoriser dans les réglages Safari.', 'error');
                    return;
                }
            }

            State.recognition.start();
            State.isRecording = true;
            if (this.elements.voiceBtn) {
                this.elements.voiceBtn.classList.add('text-red-500', 'animate-pulse');
            }
        } catch (e) {
            console.error(e);
            showToast('Erreur lors du démarrage de la reconnaissance vocale', 'error');
        }
    },

    stopRecording() {
        if (State.recognition) State.recognition.stop();
        State.isRecording = false;
        if (this.elements.voiceBtn) {
            this.elements.voiceBtn.classList.remove('text-red-500', 'animate-pulse');
        }
    },

    toggleSourcesSidebar(show) {
        const sidebar = document.getElementById('sourcesSidebar');
        const overlay = document.getElementById('sourcesOverlay');
        if (!sidebar || !overlay) return;

        if (show) {
            sidebar.classList.remove('translate-x-full');
            overlay.classList.remove('hidden', 'opacity-0');
            overlay.classList.add('opacity-100');
        } else {
            sidebar.classList.add('translate-x-full');
            overlay.classList.remove('opacity-100');
            overlay.classList.add('opacity-0');
            setTimeout(() => overlay.classList.add('hidden'), 300);
        }
    },

    renderSourcesInSidebar(chunks) {
        const container = document.getElementById('sourcesList');
        if (!container) return;

        container.innerHTML = '';
        if (!chunks || chunks.length === 0) {
            container.innerHTML = '<p class="text-sm text-gray-500 text-center">Aucune source disponible.</p>';
            return;
        }

        chunks.forEach((chunk, index) => {
            if (chunk.web && chunk.web.uri && chunk.web.title) {
                const domain = new URL(chunk.web.uri).hostname;
                const favicon = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;

                const item = document.createElement('a');
                item.href = chunk.web.uri;
                item.target = '_blank';
                item.className = 'block p-3 rounded-lg bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 transition-colors group';
                item.innerHTML = `
                    <div class="flex items-start gap-3">
                        <div class="source-favicon-wrapper group-hover:bg-white dark:group-hover:bg-gray-600 transition-colors">
                            <img src="${favicon}" class="source-favicon" alt="" onerror="this.style.display='none'">
                        </div>
                        <div class="flex-1 min-w-0">
                            <h4 class="text-sm font-medium text-blue-600 truncate dark:text-blue-400 group-hover:underline">${this.escapeHtml(chunk.web.title)}</h4>
                            <p class="text-xs text-gray-500 truncate mt-0.5">${domain}</p>
                        </div>
                    </div>
                `;
                container.appendChild(item);
            }
        });
    },

    handleAction(btn, action) {
        const content = decodeURIComponent(btn.dataset.content || '');

        if (action === 'copy') {
            this.copyToClipboard(content);
            this.showToast('Copié', 'success');
        } else if (action === 'speak') {
            this.speakText(btn, content);
        } else if (action === 'regenerate') {
            // Use the last user message, not the AI response
            setInput(State.lastUserMessage);
            document.querySelector('form').dispatchEvent(new Event('submit'));
        }
    },

    toggleSidebar() {
        const sidebar = this.elements.sidebar;
        const overlay = this.elements.sidebarOverlay;

        if (!sidebar || !overlay) return;

        const isClosed = sidebar.classList.contains('-translate-x-full');

        if (isClosed) {
            sidebar.classList.remove('-translate-x-full');
            sidebar.setAttribute('aria-hidden', 'false');
            sidebar.removeAttribute('inert');
            overlay.classList.remove('opacity-0', 'pointer-events-none');
        } else {
            sidebar.classList.add('-translate-x-full');
            sidebar.setAttribute('aria-hidden', 'true');
            sidebar.setAttribute('inert', '');
            overlay.classList.add('opacity-0', 'pointer-events-none');
        }
    },

    enhanceCodeBlocks(container) {
        container.querySelectorAll('pre code').forEach((codeBlock) => {
            const pre = codeBlock.parentElement;
            if (pre.parentElement.classList.contains('code-block-wrapper')) return;

            // Detect language
            let lang = 'Code';
            codeBlock.classList.forEach(cls => {
                if (cls.startsWith('language-')) {
                    lang = cls.replace('language-', '');
                }
            });

            // Create Wrapper
            const wrapper = document.createElement('div');
            wrapper.className = 'code-block-wrapper';

            // Create Header
            const header = document.createElement('div');
            header.className = 'code-block-header';
            header.innerHTML = `
                <span class="lang-label">${lang}</span>
                <button class="copy-btn" title="Copier le code">
                    <i class="fas fa-copy"></i>
                    <span>Copier</span>
                </button>
            `;

            // Setup Copy Event
            const copyBtn = header.querySelector('.copy-btn');
            copyBtn.onclick = (e) => {
                e.stopPropagation(); // Prevent message copy
                this.copyToClipboard(codeBlock.textContent);

                const icon = copyBtn.querySelector('i');
                const span = copyBtn.querySelector('span');

                icon.className = 'fas fa-check text-green-500';
                span.textContent = 'Copié !';
                span.className = 'text-green-500';

                setTimeout(() => {
                    icon.className = 'fas fa-copy';
                    span.textContent = 'Copier';
                    span.className = '';
                }, 2000);
            };

            // Wrap
            pre.parentNode.insertBefore(wrapper, pre);
            wrapper.appendChild(header);
            wrapper.appendChild(pre);
        });
    },

    renderSources(metadata) {
        // Sources are now handled in the actions bar / sidebar
        return '';
    },

    renderActionsBar(content, metadata) {
        let sourcesHtml = '';
        if (metadata && metadata.grounding_metadata && metadata.grounding_metadata.groundingChunks) {
            const chunks = metadata.grounding_metadata.groundingChunks;
            const validChunks = chunks.filter(c => c.web && c.web.uri && c.web.title).slice(0, 3);

            if (validChunks.length > 0) {
                const chunksData = encodeURIComponent(JSON.stringify(metadata.grounding_metadata.groundingChunks));
                sourcesHtml = `
                    <div class="flex items-center gap-1 mr-2 pr-2 border-r border-gray-200 dark:border-gray-700 cursor-pointer" 
                         onclick="UI.renderSourcesInSidebar(JSON.parse(decodeURIComponent('${chunksData}'))); UI.toggleSourcesSidebar(true)"
                         title="Voir toutes les sources">
                `;
                validChunks.forEach(chunk => {
                    const domain = new URL(chunk.web.uri).hostname;
                    const favicon = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
                    sourcesHtml += `
                        <img src="${favicon}" class="w-4 h-4 rounded-sm opacity-70 hover:opacity-100 transition-opacity" alt="Source" onerror="this.style.display='none'">
                    `;
                });
                sourcesHtml += `</div>`;
            }
        }

        const safeContent = encodeURIComponent(content);

        return `
            <div class="actions-bar flex items-center">
                ${sourcesHtml}
                <button class="action-btn" onclick="UI.handleAction(this, 'copy')" data-content="${safeContent}" title="Copier">
                    <i class="fas fa-copy"></i>
                </button>
                <button class="action-btn" onclick="UI.handleAction(this, 'speak')" data-content="${safeContent}" title="Lire à haute voix">
                    <i class="fas fa-volume-up"></i>
                </button>
                <button class="action-btn" onclick="UI.handleAction(this, 'regenerate')" data-content="${safeContent}" title="Régénérer">
                    <i class="fas fa-sync-alt"></i>
                </button>
                <div class="flex-1"></div>
                 <button class="action-btn" title="Bonne réponse">
                    <i class="far fa-thumbs-up"></i>
                </button>
                <button class="action-btn" title="Mauvaise réponse">
                    <i class="far fa-thumbs-down"></i>
                </button>
            </div>
        `;
    },

    speakText(btn, text) {
        text = text || btn.dataset.text;
        if (!text) return;

        if (window.speechSynthesis.speaking) {
            window.speechSynthesis.cancel();
            btn.querySelector('i').className = 'fas fa-volume-up';
            return;
        }

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'fr-FR';
        utterance.onend = () => {
            btn.querySelector('i').className = 'fas fa-volume-up';
        };

        btn.querySelector('i').className = 'fas fa-stop-circle text-red-500';
        window.speechSynthesis.speak(utterance);
    },

    createTypingIndicator() {
        const div = document.createElement('div');
        div.className = 'flex w-full mb-6 justify-start animate-fade-in';
        div.id = 'typingIndicator';
        div.innerHTML = `
            <div class="glass dark:bg-dark-surface p-4 rounded-2xl rounded-bl-sm border border-gray-200 dark:border-dark-border flex gap-1">
                <div class="typing-dot w-2 h-2 bg-primary-500 rounded-full"></div>
                <div class="typing-dot w-2 h-2 bg-primary-500 rounded-full"></div>
                <div class="typing-dot w-2 h-2 bg-primary-500 rounded-full"></div>
            </div>
        `;
        return div;
    },

    renderAttachments(attachments) {
        if (!attachments || attachments.length === 0) return '';

        let html = '<div class="message-attachments flex flex-wrap gap-2 mt-3">';
        attachments.forEach(att => {
            const isImage = att.type === 'image' || (att.mime_type && att.mime_type.startsWith('image/'));
            if (isImage) {
                html += `
                    <div class="attachment-preview-item group relative">
                        <a href="${att.url}" target="_blank" class="block">
                            <img src="${att.url}" class="w-32 h-32 object-cover rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm hover:ring-2 hover:ring-primary-500 transition-all" alt="${att.name}">
                        </a>
                        <div class="absolute bottom-0 left-0 right-0 p-1 bg-black/60 text-white text-[10px] truncate rounded-b-lg opacity-0 group-hover:opacity-100 transition-opacity">
                            ${att.name}
                        </div>
                    </div>
                `;
            } else {
                html += `
                    <a href="${att.url}" target="_blank" class="attachment-file-item flex items-center gap-2 p-2 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors border border-gray-200 dark:border-gray-700 max-w-[200px]">
                        <div class="w-8 h-8 flex items-center justify-center bg-primary-100 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 rounded">
                            <i class="fas fa-file-alt"></i>
                        </div>
                        <div class="flex flex-col min-w-0">
                            <span class="text-xs font-medium truncate">${att.name}</span>
                            <span class="text-[10px] text-gray-500">${Math.round(att.size / 1024) || 1} KB</span>
                        </div>
                    </a>
                `;
            }
        });
        html += '</div>';
        return html;
    },

    renderMath(element) {
        if (!window.renderMathInElement) return;

        try {
            renderMathInElement(element, {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '$', right: '$', display: false },
                    { left: '\\(', right: '\\)', display: false },
                    { left: '\\[', right: '\\]', display: true }
                ],
                throwOnError: false,
                output: 'html',
                strict: false
            });
        } catch (e) {
            console.error("KaTeX Render Error:", e);
        }
    },

    createMessageElement(content, isUser, attachments = [], metadata = {}) {
        const messageGroup = document.createElement('div');

        if (isUser) {
            // === USER MESSAGE (Aligned Right, Gray Background) ===
            messageGroup.className = 'message-group user-message mb-6 flex flex-col items-end animate-slide-up';

            const contentWrapper = document.createElement('div');
            contentWrapper.className = 'inline-block max-w-[85%] sm:max-w-[75%] bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-50 rounded-2xl rounded-tr-sm px-4 py-3 shadow-sm border border-gray-200 dark:border-gray-700';

            let innerHtml = '';
            if (content) {
                innerHtml = `<div class="whitespace-pre-wrap text-sm leading-relaxed">${this.escapeHtml(content)}</div>`;
            }

            // Add attachments to user message
            innerHtml += this.renderAttachments(attachments);

            contentWrapper.innerHTML = innerHtml;
            messageGroup.appendChild(contentWrapper);

        } else {
            // === AI MESSAGE (Full Width, No Background) ===
            messageGroup.className = 'message-group ai-message mb-6 w-full animate-slide-up';

            try {
                const processedContent = this.formatAIContent(content, attachments);
                const parsedMarkdown = marked.parse(processedContent);
                const cleanHtml = DOMPurify.sanitize(parsedMarkdown, {
                    ALLOWED_TAGS: [
                        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'p', 'a', 'ul', 'ol',
                        'li', 'b', 'i', 'strong', 'em', 'strike', 'code', 'hr', 'br', 'div',
                        'table', 'thead', 'tbody', 'tr', 'th', 'td', 'pre', 'span', 'img', 'kbd'
                    ],
                    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'target', 'rel', 'data-language', 'data-filename', 'data-task-id'],
                    ALLOW_DATA_ATTR: true
                });

                const contentWrapper = document.createElement('div');
                contentWrapper.className = 'relative group py-2';

                contentWrapper.innerHTML = `
                    <div class="markdown-body prose dark:prose-invert max-w-none prose-headings:font-bold prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-code:text-pink-600 dark:prose-code:text-pink-400">
                        ${cleanHtml}
                    </div>
                `;

                // Add attachments if not empty and not already in-line
                if (content && attachments && attachments.length > 0) {
                    const uploadedAttachments = attachments.filter(a => !a.task_id);
                    if (uploadedAttachments.length > 0) {
                        contentWrapper.innerHTML += this.renderAttachments(uploadedAttachments);
                    }
                }

                // Add Sources if available
                if (metadata && metadata.grounding_metadata) {
                    contentWrapper.innerHTML += this.renderSources(metadata.grounding_metadata);
                }

                // Add Actions Bar
                contentWrapper.innerHTML += this.renderActionsBar(content, metadata);

                // Enhance Code Blocks
                this.enhanceCodeBlocks(contentWrapper);

                // Highlight code blocks
                // Marked is configured to highlight, so we don't need manual highlighting here
                // contentWrapper.querySelectorAll('pre code').forEach((block) => {
                //    hljs.highlightElement(block);
                // });

                // Render Math
                this.renderMath(contentWrapper);

                messageGroup.appendChild(contentWrapper);

                // Start Polling
                setTimeout(() => {
                    contentWrapper.querySelectorAll('.ai-image-container').forEach(container => {
                        const taskId = container.dataset.taskId;
                        if (taskId) this.pollImageStatus(taskId, container);
                    });
                }, 100);

            } catch (error) {
                console.error('Erreur lors du rendu du message:', error);
                messageGroup.innerHTML = `
                    <div class="text-red-500 text-sm">Une erreur est survenue lors de l'affichage.</div>
                    <div class="mt-2 p-2 bg-red-50 dark:bg-red-900/20 rounded text-sm">${this.escapeHtml(content)}</div>
                `;
            }
        }
        return messageGroup;
    },

    showWebSearchLoader() {
        const container = document.getElementById('dynamicLoaders');
        if (!container) return;

        const loader = document.createElement('div');
        loader.id = 'webSearchLoader';
        loader.className = 'loader-container web-search-loader';
        loader.innerHTML = `
    <i class="fas fa-globe loader-icon"></i>
    <span class="text-sm font-medium">Recherche d'informations en cours...</span>
`;
        container.appendChild(loader);
    },

    hideWebSearchLoader() {
        const loader = document.getElementById('webSearchLoader');
        if (loader) {
            loader.classList.add('fade-out');
            setTimeout(() => loader.remove(), 300);
        }
    },

    showImageGenLoader() {
        const container = document.getElementById('dynamicLoaders');
        if (!container) return;

        const loader = document.createElement('div');
        loader.id = 'imageGenLoader';
        loader.className = 'loader-container image-gen-loader';
        loader.innerHTML = `
    <i class="fas fa-magic loader-icon"></i>
        <span class="text-sm font-medium">Génération de l'image éducative...</span>
`;
        container.appendChild(loader);
    },

    hideImageGenLoader() {
        const loader = document.getElementById('imageGenLoader');
        if (loader) {
            loader.classList.add('fade-out');
            setTimeout(() => loader.remove(), 300);
        }
    },

    async typeAIStream(content, container, attachments = [], metadata = {}) {
        const words = content.split(' ');
        let currentText = '';

        // Créer l'élément de message AI vide
        const messageEl = this.createMessageElement('', false, attachments);
        container.appendChild(messageEl);
        const contentDiv = messageEl.querySelector('.markdown-body');

        for (let i = 0; i < words.length; i++) {
            currentText += words[i] + ' ';

            // Format content with images if valid tags are complete
            const processedText = this.formatAIContent(currentText, attachments);
            contentDiv.innerHTML = marked.parse(processedText);

            // Render attachments at the bottom of AI message if not already handled by formatAIContent
            // (Note: attachments generated by AI are handled by formatAIContent tags, 
            // but provided attachments should be visible too)
            if (i === words.length - 1 && attachments && attachments.length > 0) {
                // Only append if they aren't [IMAGE_EDUCATIVE] results
                const uploadedAttachments = attachments.filter(a => !a.task_id);
                if (uploadedAttachments.length > 0) {
                    contentDiv.innerHTML += this.renderAttachments(uploadedAttachments);
                }
            }

            // Enhance Code Blocks
            this.enhanceCodeBlocks(contentDiv);

            // Re-highlight code blocks if any - Removed to prevent conflict with marked
            // contentDiv.querySelectorAll('pre code').forEach((block) => {
            //    hljs.highlightElement(block);
            // });

            this.scrollToBottom();
            // Délai pour l'effet de streaming
            await new Promise(resolve => setTimeout(resolve, 30 + Math.random() * 20)); // Keep streaming fast
        }

        // Fin du streaming : Ajouter les Sources et la barre d'action
        if (metadata && metadata.grounding_metadata) {
            contentDiv.innerHTML += this.renderSources(metadata.grounding_metadata);
        }

        contentDiv.innerHTML += this.renderActionsBar(content, metadata);

        // Final Math Render
        this.renderMath(contentDiv);

        // Start Polling for images after stream is done
        contentDiv.querySelectorAll('.ai-image-container').forEach(container => {
            const taskId = container.dataset.taskId;
            if (taskId) this.pollImageStatus(taskId, container);
        });
    },

    formatAIContent(content, attachments = []) {
        let processed = content;

        // Replace Intelitech tool calls with a togglable block
        // Format: [INTELLITECH_TOOL: tool_name, {json}]
        const toolPattern = /\[INTELLITECH_TOOL:\s*([\w_]+)\s*,\s*([\s\S]*?)\]/gi;
        processed = processed.replace(toolPattern, (match, toolName, payload) => {
            const raw = `${toolName}, ${payload}`.trim();
            const safe = this.escapeHtml(raw);
            return `
<div class="intellitech-tool-call">
  <div class="intellitech-tool-placeholder">Outil Intelitech (caché)</div>
  <pre class="intellitech-tool-raw"><code>${safe}</code></pre>
</div>
`;
        });

        // Match [Image en cours de génération: FILENAME]
        const imagePattern = /\[Image en cours de génération: ([^\]]+)\]/g;
        processed = processed.replace(imagePattern, (match, filename) => {
            // Find task_id in attachments if available
            const att = (attachments || []).find(a => a.name === filename);
            const taskId = att ? att.task_id : '';

            return `<div class="ai-image-container" data-filename="${filename}" data-task-id="${taskId}">
                <img src="/api/ai/image/${filename}" class="ai-image-final" onerror="this.style.display='none'" onload="this.style.display='block'; this.classList.add('loaded')">
                <div class="ai-image-placeholder">
                    <i class="fas fa-spinner fa-spin"></i>
                    <span> génération en cours...</span>
                </div>
            </div>`;
        });

        return processed;
    },

    async pollImageStatus(taskId, container) {
        let attempts = 0;
        const maxAttempts = 60; // 2 minutes approx
        const img = container.querySelector('.ai-image-final');
        const placeholderText = container.querySelector('.ai-image-placeholder span');

        const check = async () => {
            try {
                const response = await axios.get(`/api/ai/image-status/${taskId}`);
                const data = response.data;

                if (data.status === 'completed') {
                    // Image ready! Update src to force reload if needed
                    const filename = container.dataset.filename;
                    img.src = `/api/ai/image/${filename}?t=${new Date().getTime()}`;
                    img.style.display = 'block';
                    img.classList.add('loaded');
                    return;
                } else if (data.status === 'failed') {
                    placeholderText.textContent = "Échec de la génération";
                    container.querySelector('i').className = 'fas fa-exclamation-triangle text-red-500';
                    return;
                }

                attempts++;
                if (attempts < maxAttempts) {
                    setTimeout(check, 2000);
                } else {
                    placeholderText.textContent = "Temps expiré";
                }
            } catch (error) {
                console.error('Polling error:', error);
                setTimeout(check, 5000);
            }
        };

        check();
    },

    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    },

    showToast(message, type = 'info') {
        const container = this.elements.toastContainer;
        if (!container) return;

        const el = document.createElement('div');
        el.className = 'pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg transform transition-all duration-300 translate-x-full opacity-0';

        const colors = {
            success: 'bg-green-500 text-white',
            error: 'bg-red-500 text-white',
            warning: 'bg-yellow-500 text-white',
            info: 'bg-primary-500 text-white'
        };
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        const colorClass = colors[type] || colors.info;
        el.className += ' ' + colorClass;

        el.innerHTML = `
            <i class="fas ${icons[type] || icons.info} text-lg"></i>
            <span class="text-sm font-medium">${message}</span>
        `;

        container.appendChild(el);

        // Animate in
        requestAnimationFrame(() => {
            el.classList.remove('translate-x-full', 'opacity-0');
        });

        // Hide after 3s
        setTimeout(() => {
            el.classList.add('translate-x-full', 'opacity-0');
            setTimeout(() => el.remove(), 300);
        }, 3000);
    },

    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    },

    setupSpeechRecognition() {
        if ('webkitSpeechRecognition' in window) {
            State.recognition = new webkitSpeechRecognition();
            State.recognition.continuous = true;
            State.recognition.interimResults = true;
            State.recognition.lang = 'fr-FR';

            State.recognition.onstart = () => {
                State.isRecording = true;
                if (this.elements.voiceBtn) {
                    this.elements.voiceBtn.classList.remove('text-gray-400');
                    this.elements.voiceBtn.classList.add('text-red-500', 'animate-pulse');
                }
            };

            State.recognition.onend = () => {
                State.isRecording = false;
                if (this.elements.voiceBtn) {
                    this.elements.voiceBtn.classList.add('text-gray-400');
                    this.elements.voiceBtn.classList.remove('text-red-500', 'animate-pulse');
                }
            };

            State.recognition.onresult = (event) => {
                let interimTranscript = '';
                let finalTranscript = '';

                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript;
                    } else {
                        interimTranscript += event.results[i][0].transcript;
                    }
                }

                if (finalTranscript) {
                    this.elements.input.value += finalTranscript + ' ';
                    this.adjustTextareaHeight();
                }
            };

            State.recognition.onerror = (event) => {
                console.error('Speech recognition error', event.error);
                this.toggleRecording(); // Stop on error
                // Ignore no-speech errors as they are common
                if (event.error !== 'no-speech') {
                    this.showToast('Erreur reconnaissance vocale: ' + event.error, 'error');
                }
            };
        } else {
            console.warn('Web Speech API not supported');
            this.showToast('Votre navigateur ne supporte pas la reconnaissance vocale', 'error');
            if (this.elements.voiceBtn) this.elements.voiceBtn.style.display = 'none';
        }
    },

    toggleRecording() {
        if (!State.recognition) return;

        if (State.isRecording) {
            State.recognition.stop();
        } else {
            State.recognition.start();
        }
    },

    scrollToBottom() {
        const container = this.elements.messages;
        if (container) container.scrollTop = container.scrollHeight;
    },

    renderPreviews() {
        const previewContainer = document.getElementById('attachmentPreview');
        if (!previewContainer) return;

        const attachments = State.pendingAttachments || [];
        if (attachments.length === 0) {
            previewContainer.innerHTML = '';
            previewContainer.classList.add('hidden');
            return;
        }

        previewContainer.classList.remove('hidden');
        previewContainer.innerHTML = attachments.map((att, index) => `
            <div class="preview-item">
                <div class="preview-remove" onclick="UI.removeAttachment(${index})">
                    <i class="fas fa-times"></i>
                </div>
                ${att.type === 'image'
                ? `<img src="${att.url}" alt="${att.name}">`
                : `<div class="file-icon"><i class="fas ${this.getFileIcon(att.name)}"></i></div>`
            }
            </div>
        `).join('');
    },

    removeAttachment(index) {
        if (State.pendingAttachments) {
            State.pendingAttachments.splice(index, 1);
            this.renderPreviews();

            if (State.pendingAttachments.length === 0 && this.elements.attachBtn) {
                this.elements.attachBtn.classList.remove('text-green-500', 'text-blue-500');
                this.elements.attachBtn.classList.add('text-gray-400');
            }
        }
    },

    getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const icons = {
            pdf: 'fa-file-pdf',
            doc: 'fa-file-word',
            docx: 'fa-file-word',
            txt: 'fa-file-alt',
            csv: 'fa-file-csv',
            xls: 'fa-file-excel',
            xlsx: 'fa-file-excel',
            zip: 'fa-file-archive',
            rar: 'fa-file-archive'
        };
        return icons[ext] || 'fa-file';
    },

    adjustTextareaHeight() {
        const textarea = this.elements.input;
        if (!textarea) return;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    },

    setupEventListeners() {
        if (this.elements.form) {
            this.elements.form.addEventListener('submit', this.handleSubmit.bind(this));
        }

        if (this.elements.themeToggle) {
            this.elements.themeToggle.addEventListener('click', () => this.toggleTheme());
            this.updateThemeToggleIcon(); // Set initial icon state
        }

        if (this.elements.input) {
            this.elements.input.addEventListener('input', () => this.adjustTextareaHeight());
            this.elements.input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (this.elements.form) this.elements.form.dispatchEvent(new Event('submit'));
                }
            });
        }

        if (this.elements.sidebarToggle) {
            this.elements.sidebarToggle.addEventListener('click', () => this.toggleSidebar());
        }

        if (this.elements.sidebarOverlay) {
            this.elements.sidebarOverlay.addEventListener('click', () => this.toggleSidebar());
        }

        if (this.elements.themeToggle) {
            this.elements.themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        if (this.elements.voiceBtn) {
            this.elements.voiceBtn.addEventListener('click', () => this.toggleRecording());
        }

        // Handle attachment button & file input
        if (this.elements.attachBtn && this.elements.fileInput) {
            this.elements.attachBtn.addEventListener('click', () => this.elements.fileInput.click());

            this.elements.fileInput.addEventListener('change', async (e) => {
                const files = e.target.files;
                if (!files || files.length === 0) return;

                // Initialize pending attachments if not exists
                if (!State.pendingAttachments) State.pendingAttachments = [];

                // Visual feedback of upload start
                this.elements.attachBtn.classList.add('text-blue-500', 'animate-pulse');
                this.showToast('Upload en cours...', 'info');

                try {
                    for (let i = 0; i < files.length; i++) {
                        const file = files[i];
                        // Determine preset based on type, defaulting to 'documents_upload' for generic files
                        // But since chat accepts images too, we might need logic.
                        // cloudinary_uploader.js has specific presets: profiles_upload, documents_upload, html_upload, assets_upload.
                        // 'auto' resource type usually works well with a generic unsigned preset if enabled.
                        // Assuming 'documents_upload' works for general files or use 'auto' logic if backend expects it.
                        // Let's use 'documents_upload' which seemed to be the general one, or 'auto' if configured.
                        // Actually, 'documents_upload' was for resources.
                        // Let's check file type.
                        let preset = 'documents_upload';
                        let resourceType = 'auto';

                        // Proceed with upload
                        const result = await uploadToCloudinary(file, preset, resourceType);

                        State.pendingAttachments.push({
                            type: file.type.startsWith('image/') ? 'image' : 'file',
                            name: file.name,
                            url: result.secure_url,
                            size: result.bytes,
                            mime_type: file.type || result.format || 'application/octet-stream'
                        });
                    }

                    this.renderPreviews();
                    this.showToast(`${files.length} fichier(s) prêt(s) à l'envoi`, 'success');
                    this.elements.attachBtn.classList.remove('animate-pulse');
                    this.elements.attachBtn.classList.add('text-green-500'); // Indicate success

                } catch (error) {
                    console.error('Upload failed:', error);
                    this.showToast("Erreur lors de l'upload: " + error.message, 'error');
                    this.elements.attachBtn.classList.remove('text-blue-500', 'animate-pulse');
                }
            });
        }

        const newChatBtn = document.getElementById('newChat');
        if (newChatBtn) {
            newChatBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.clearActiveConversation();
                window.history.pushState({}, '', '/ai/chat');
                this.elements.welcome ? this.elements.welcome.style.display = 'flex' : null;
            });
        }
    },

    async handleSubmit(e) {
        e.preventDefault();
        if (State.isTyping) return;

        const input = this.elements.input;
        const message = input.value.trim();
        const attachments = State.pendingAttachments || [];

        if (!message && attachments.length === 0) {
            return;
        }

        // Store the user message for regeneration
        if (message) {
            State.lastUserMessage = message;
        }

        // Hide welcome screen
        if (this.elements.welcome) {
            this.elements.welcome.style.display = 'none';
        }

        // Add User Message (Text & Attachments)
        this.elements.messages.appendChild(this.createMessageElement(message, true, attachments));

        this.scrollToBottom();

        // Clear Input
        input.value = '';
        this.adjustTextareaHeight();
        if (this.elements.attachBtn) {
            this.elements.attachBtn.classList.remove('text-green-500', 'text-blue-500');
            this.elements.attachBtn.classList.add('text-gray-400');
        }
        // Clear pending attachments
        State.pendingAttachments = [];
        if (this.elements.fileInput) this.elements.fileInput.value = '';
        this.renderPreviews();

        State.isTyping = true;

        // Show Typing Indicator
        const typingObj = this.createTypingIndicator();
        this.elements.messages.appendChild(typingObj);
        this.scrollToBottom();

        try {
            // Construct payload
            const payload = {
                message: message,
                conversation_id: State.currentConversationId,
                attachments: attachments
            };

            const response = await fetch(CONFIG.endpoints.chat, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CONFIG.csrfToken
                },
                body: JSON.stringify(payload)
            });

            // Remove Typing Indicator
            typingObj.remove();

            if (!response.ok) {
                const errData = await response.json();
                this.showToast(errData.error || 'Network response was not ok', 'error');
                throw new Error(errData.error || 'Network response was not ok');
            }

            const data = await response.json();

            // Update conversation ID if returned
            if (data.conversation_id) {
                State.currentConversationId = data.conversation_id;
            }

            // Gérer les loaders dynamiques basés sur la réponse
            if (data.has_web_search) {
                this.showWebSearchLoader();
                await new Promise(resolve => setTimeout(resolve, 1500)); // Petit délai pour l'effet visuel
                this.hideWebSearchLoader();
            }

            if (data.has_image_generation) {
                this.showImageGenLoader();
            }

            // Note: The API returns { success: true, response: "AI Message...", ... }
            const aiContent = data.response || data.message || "Je ne sais pas quoi répondre. veuillez réessayer";

            // Add AI Message with Streaming Effect
            await this.typeAIStream(aiContent, this.elements.messages, data.attachments || [], data);

            if (data.has_image_generation) {
                // Si une image est en cours, on pourrait attendre ou laisser le polling (existant peut-être) faire le job
                // Ici on cache juste le loader après le texte
                setTimeout(() => this.hideImageGenLoader(), 2000);
            }

            this.scrollToBottom();

            // Highlight Code Blocks
            // hljs.highlightAll(); // Removed

        } catch (error) {
            console.error('Error:', error);
            typingObj.remove();
            this.elements.messages.appendChild(this.createMessageElement(`Désolé, une erreur est survenue: ${error.message}`, false));
            this.scrollToBottom();
        } finally {
            State.isTyping = false;
        }
    }
};

// Global Helper for Welcome Buttons
window.setInput = (text) => {
    const input = document.querySelector('#userInput');
    if (input) {
        input.value = text;
        input.focus();
        UI.adjustTextareaHeight();
    }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => UI.init());
