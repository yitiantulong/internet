(() => {
    const STORAGE_KEY = "neoblog-theme";
    const root = document.documentElement;
    const toggleButton = document.getElementById("themeToggle");
    const assistant = document.getElementById("pageAssistant");
    const assistantMessage = document.getElementById("assistantMessage");

    function setTheme(theme) {
        root.classList.remove("theme-light", "theme-dark");
        root.classList.add(theme);
        localStorage.setItem(STORAGE_KEY, theme);
        if (assistantMessage) {
            assistantMessage.textContent = theme === "theme-dark"
                ? "夜间模式已开启，放松双眼更舒适。"
                : "切换回亮色模式，继续发现精彩内容！";
        }
    }

    function detectPreferredTheme() {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            return stored;
        }
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "theme-dark" : "theme-light";
    }

    function toggleTheme() {
        const current = root.classList.contains("theme-dark") ? "theme-dark" : "theme-light";
        const next = current === "theme-dark" ? "theme-light" : "theme-dark";
        setTheme(next);
    }

    function initAssistant() {
        if (!assistant) {
            return;
        }
        const faces = [
            "assistant-default.svg",
            "assistant-happy.svg",
            "assistant-idea.svg",
            "assistant-wink.svg",
        ];
        let faceIndex = 0;
        const avatar = assistant.querySelector(".assistant-avatar img");
        const actionButton = document.getElementById("assistantAction");

        function cycleFace() {
            faceIndex = (faceIndex + 1) % faces.length;
            if (avatar) {
                avatar.src = `/static/images/${faces[faceIndex]}`;
            }
        }

        assistant.addEventListener("mouseenter", cycleFace);
        assistant.addEventListener("mouseleave", cycleFace);

        if (actionButton) {
            actionButton.addEventListener("click", () => {
                assistant.classList.add("assistant-pulse");
                setTimeout(() => assistant.classList.remove("assistant-pulse"), 1200);
                const event = new CustomEvent("assistant:action", { detail: { type: "prompt" } });
                window.dispatchEvent(event);
            });
        }
    }

    function surroundSelection(textarea, before, after, placeholder = "") {
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const value = textarea.value;
        const selected = value.substring(start, end) || placeholder;
        const replacement = `${before}${selected}${after}`;
        textarea.value = value.substring(0, start) + replacement + value.substring(end);
        const cursor = start + replacement.length;
        textarea.focus();
        textarea.setSelectionRange(cursor, cursor - (placeholder ? after.length : 0));
    }

    function initEditorToolbar() {
        document.querySelectorAll("[data-role='editor-toolbar']").forEach((toolbar) => {
            const targetSelector = toolbar.getAttribute("data-target");
            const textarea = targetSelector ? document.querySelector(targetSelector) : null;
            if (!textarea) {
                return;
            }
            toolbar.querySelectorAll("button[data-command]").forEach((button) => {
                button.addEventListener("click", () => {
                    const command = button.getAttribute("data-command");
                    switch (command) {
                        case "bold":
                            surroundSelection(textarea, "**", "**", "加粗文本");
                            break;
                        case "italic":
                            surroundSelection(textarea, "*", "*", "斜体文本");
                            break;
                        case "heading":
                            surroundSelection(textarea, "\n# ", "\n", "标题");
                            break;
                        case "quote":
                            surroundSelection(textarea, "\n> ", "\n", "引用内容");
                            break;
                        case "code":
                            surroundSelection(textarea, "\n```\n", "\n```\n", "代码块");
                            break;
                        case "list":
                            surroundSelection(textarea, "\n- ", "\n", "列表项");
                            break;
                        case "link": {
                            const url = window.prompt("请输入链接地址：", "https://");
                            if (url) {
                                surroundSelection(textarea, "[", `](${url})`, "链接文本");
                            }
                            break;
                        }
                        default:
                            break;
                    }
                });
            });
        });
    }

    function escapeHtml(text) {
        if (typeof text !== "string") {
            return "";
        }
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function escapeAttr(text) {
        if (typeof text !== "string") {
            return "";
        }
        return text.replace(/"/g, "&quot;");
    }

    function renderConversationMessages(container, conversation, currentUserId) {
        if (!Array.isArray(conversation) || conversation.length === 0) {
            container.innerHTML = '<div class="alert alert-light border-dashed text-muted" role="alert">暂未开始对话，发送第一条私信吧！</div>';
            return;
        }
        const fragments = conversation.map((msg) => {
            const isSelf = Number(msg.sender_id) === Number(currentUserId);
            const roleClass = isSelf ? "message-bubble--self" : "message-bubble--other";
            const senderLabel = isSelf ? "我" : escapeHtml(msg.sender.display_name || msg.sender.username || "");
            const created = escapeHtml(msg.created_at || "");
            const content = escapeHtml(msg.content || "").replace(/\n/g, "<br>");
            return (
                `<div class="message-bubble ${roleClass}">` +
                `<div class="message-body">` +
                `<span class="message-sender">${senderLabel}</span>` +
                `<div class="message-text">${content}</div>` +
                `<span class="message-time">${created}</span>` +
                `</div>` +
                `</div>`
            );
        });
        container.innerHTML = `<div class="message-thread">${fragments.join("")}</div>`;
    }

    function initMessagesView() {
        const listContainer = document.querySelector("[data-role='conversation-list']");
        const messagesContainer = document.getElementById("conversationMessages");
        const headerEl = document.getElementById("conversationHeader");
        const form = document.getElementById("conversationForm");
        const targetInput = document.getElementById("conversationTarget");
        if (!listContainer || !messagesContainer || !headerEl || !form || !targetInput) {
            return;
        }
        const currentUserId = Number(messagesContainer.dataset.userId || "0");

        function setActiveContact(username) {
            listContainer.querySelectorAll("[data-username]").forEach((link) => {
                if (link.dataset.username === username) {
                    link.classList.add("active");
                } else {
                    link.classList.remove("active");
                }
            });
        }

        async function loadConversation(username, displayName) {
            try {
                const response = await fetch(`/api/messages/${encodeURIComponent(username)}`);
                if (!response.ok) {
                    throw new Error(`请求失败：${response.status}`);
                }
                const payload = await response.json();
                if (!payload.success) {
                    throw new Error(payload.message || "获取对话失败");
                }
                renderConversationMessages(messagesContainer, payload.conversation, currentUserId);
                headerEl.textContent = `与 ${displayName} 的对话`;
                targetInput.value = username;
                setActiveContact(username);
            } catch (error) {
                messagesContainer.innerHTML = `<div class="alert alert-danger" role="alert">${error.message}</div>`;
            }
        }

        listContainer.querySelectorAll("[data-username]").forEach((link) => {
            link.addEventListener("click", (event) => {
                event.preventDefault();
                const username = link.dataset.username;
                const displayName = link.dataset.displayName || username;
                loadConversation(username, displayName);
            });
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        setTheme(detectPreferredTheme());
        initAssistant();
        if (toggleButton) {
            toggleButton.addEventListener("click", toggleTheme);
        }
        initEditorToolbar();
        initMessagesView();

        const permissionSelect = document.getElementById("permission-type");
        const passwordField = document.querySelector("[data-role='password-field']");
        const passwordInput = document.getElementById("access-password");
        const passwordHint = document.getElementById("password-hint");

        if (permissionSelect && passwordField) {
            const togglePasswordField = () => {
                const isPassword = permissionSelect.value === "password";
                passwordField.classList.toggle("d-none", !isPassword);
                if (passwordInput) {
                    passwordInput.disabled = !isPassword;
                }
                if (passwordHint) {
                    passwordHint.disabled = !isPassword;
                }
            };
            togglePasswordField();
            permissionSelect.addEventListener("change", togglePasswordField);
        }
    });
})();

