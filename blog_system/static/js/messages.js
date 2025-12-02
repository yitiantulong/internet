(function () {
    var currentUserId = null;
    var currentConversationUsername = null;
    var messagePollInterval = null;
    var conversationList = null;
    var conversationView = null;

    function escapeHTML(text) {
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

    function buildMessageHTML(item, currentUserId) {
        var isSelf = item.sender_id === currentUserId;
        var roleClass = isSelf ? "message-bubble--self" : "message-bubble--other";
        var senderName = isSelf
            ? "我"
            : escapeHTML(item.sender.display_name || item.sender.username || "");
        var content = escapeHTML(item.content || "").replace(/\n/g, "<br>");
        var timestamp = escapeHTML(item.created_at || "");
        return (
            '<div class="message-bubble ' +
            roleClass +
            '">' +
            '<div class="message-body">' +
            '<span class="message-sender">' +
            senderName +
            "</span>" +
            '<div class="message-text">' +
            content +
            "</div>" +
            '<span class="message-time">' +
            timestamp +
            "</span>" +
            "</div>" +
            "</div>"
        );
    }

    function loadConversation(username, displayName) {
        if (!username) {
            return;
        }
        currentConversationUsername = username;
        setActiveConversation(username);
        conversationView.innerHTML = '<div class="text-center text-muted py-4"><i class="fa-solid fa-spinner fa-spin"></i> 加载中...</div>';

        fetch("/api/messages/" + encodeURIComponent(username))
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("加载对话失败");
                }
                return response.json();
            })
            .then(function (data) {
                if (!data || data.success === false) {
                    throw new Error(data.message || "获取对话失败");
                }
                var header = '<div class="d-flex align-items-center justify-content-between mb-3 pb-3 border-bottom">' +
                    '<h3 class="h6 mb-0"><i class="fa-regular fa-user-circle me-2 text-primary"></i>' + escapeHTML(displayName) + '</h3>' +
                    '<button type="button" class="btn btn-sm btn-outline-primary" data-bs-toggle="modal" data-bs-target="#newMessageModal">' +
                    '<i class="fa-solid fa-paper-plane-top me-1"></i>发送消息</button>' +
                    '</div>';
                var messagesHTML = "";
                if (Array.isArray(data.conversation) && data.conversation.length > 0) {
                    var currentUserId = typeof data.current_user_id === "number" ? data.current_user_id : -1;
                    messagesHTML = '<div class="message-thread mb-3">' +
                        data.conversation.map(function (item) {
                            return buildMessageHTML(item, currentUserId);
                        }).join("") +
                        "</div>";
                } else {
                    messagesHTML = '<div class="alert alert-light mb-3" role="alert">暂未开始对话，发送第一条私信吧！</div>';
                }
                var formHTML = '<form id="conversationForm" class="mt-3">' +
                    '<input type="hidden" name="target" value="' + escapeHTML(username) + '">' +
                    '<div class="input-group">' +
                    '<textarea class="form-control" name="content" rows="3" required placeholder="输入消息内容..."></textarea>' +
                    '<button type="submit" class="btn btn-primary">' +
                    '<i class="fa-solid fa-paper-plane-top"></i></button>' +
                    '</div>' +
                    '</form>';
                conversationView.innerHTML = header + messagesHTML + formHTML;
                var thread = conversationView.querySelector(".message-thread");
                if (thread) {
                    thread.scrollTop = thread.scrollHeight;
                }
                var form = document.getElementById("conversationForm");
                if (form) {
                    form.addEventListener("submit", handleSendMessage);
                }
                startMessagePolling(username);
            })
            .catch(function (error) {
                var errorMsg = error && error.message ? error.message : "暂时无法载入对话，请稍后重试。";
                conversationView.innerHTML =
                    '<div class="alert alert-danger" role="alert">' + escapeHTML(errorMsg) + "</div>";
            });
    }

    function setActiveConversation(username) {
        if (conversationList) {
            conversationList.querySelectorAll(".conversation-item").forEach(function (item) {
                if (item.getAttribute("data-username") === username) {
                    item.classList.add("active");
                } else {
                    item.classList.remove("active");
                }
            });
        }
    }

    function startMessagePolling(username) {
        if (messagePollInterval) {
            clearInterval(messagePollInterval);
        }
        currentConversationUsername = username;
        messagePollInterval = setInterval(function () {
            if (currentConversationUsername) {
                fetch("/api/messages/" + encodeURIComponent(currentConversationUsername))
                    .then(function (response) {
                        if (!response.ok) {
                            return null;
                        }
                        return response.json();
                    })
                    .then(function (data) {
                        if (data && data.success && Array.isArray(data.conversation)) {
                            var messagesContainer = conversationView.querySelector(".message-thread");
                            if (messagesContainer) {
                                var currentUserId = typeof data.current_user_id === "number" ? data.current_user_id : -1;
                                var html = data.conversation
                                    .map(function (item) {
                                        return buildMessageHTML(item, currentUserId);
                                    })
                                    .join("");
                                messagesContainer.innerHTML = html;
                                messagesContainer.scrollTop = messagesContainer.scrollHeight;
                            }
                        }
                    })
                    .catch(function () {
                    });
            }
        }, 3000);
    }

    function stopMessagePolling() {
        if (messagePollInterval) {
            clearInterval(messagePollInterval);
            messagePollInterval = null;
        }
        currentConversationUsername = null;
    }

    function handleSendMessage(event) {
        event.preventDefault();
        var form = event.target;
        var formData = new FormData(form);
        var target = formData.get("target");
        var content = formData.get("content");
        if (!target || !content) {
            return;
        }
        fetch("/api/messages", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                target: target,
                content: content,
            }),
        })
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                if (data && data.success) {
                    var textarea = form.querySelector('textarea[name="content"]');
                    if (textarea) {
                        textarea.value = "";
                    }
                    var displayName = document.querySelector('[data-username="' + target + '"]')?.getAttribute("data-display-name") || target;
                    loadConversation(target, displayName);
                    refreshConversationList();
                } else {
                    alert("发送失败：" + (data.message || "未知错误"));
                }
            })
            .catch(function (error) {
                alert("发送失败：" + (error.message || "网络错误"));
            });
    }

    function refreshConversationList() {
        fetch("/api/messages")
            .then(function (response) {
                if (!response.ok) {
                    return null;
                }
                return response.json();
            })
            .then(function (data) {
                if (data && data.success && Array.isArray(data.messages)) {
                    var contacts = {};
                    data.messages.forEach(function (message) {
                        var other = message.sender_id === currentUserId ? message.receiver : message.sender;
                        if (other && other.username) {
                            if (!contacts[other.username]) {
                                contacts[other.username] = {
                                    username: other.username,
                                    display_name: other.display_name || other.username,
                                };
                            }
                        }
                    });
                    var contactsList = Object.values(contacts);
                    if (contactsList.length === 0) {
                        conversationList.innerHTML = '<div class="alert alert-light border-dashed text-muted" role="alert">暂无私信联系人，点击"新建私信"开始对话。</div>';
                    } else {
                        var items = contactsList.map(function (contact) {
                            var username = escapeHTML(contact.username);
                            var displayName = escapeHTML(contact.display_name);
                            var isActive = currentConversationUsername === contact.username;
                            var classes = "list-group-item list-group-item-action d-flex align-items-center justify-content-between conversation-item";
                            if (isActive) {
                                classes += " active";
                            }
                            return '<a class="' + classes + '" href="#" data-username="' + username + '" data-display-name="' + displayName + '" data-role="open-conversation">' +
                                '<div class="d-flex align-items-center gap-2">' +
                                '<i class="fa-regular fa-user-circle text-primary"></i>' +
                                '<span>' + displayName + '</span>' +
                                '</div>' +
                                '</a>';
                        }).join("");
                        conversationList.innerHTML = '<div class="list-group list-group-flush">' + items + "</div>";
                        attachConversationListeners();
                    }
                }
            })
            .catch(function () {
            });
    }

    function attachConversationListeners() {
        if (conversationList) {
            conversationList.querySelectorAll("[data-role='open-conversation']").forEach(function (link) {
                link.addEventListener("click", function (event) {
                    event.preventDefault();
                    var username = link.getAttribute("data-username");
                    var displayName = link.getAttribute("data-display-name") || username;
                    if (username) {
                        loadConversation(username, displayName);
                    }
                });
            });
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        conversationList = document.getElementById("conversationList");
        conversationView = document.getElementById("conversationView");
        
        var userIdElement = conversationList ? conversationList.querySelector("[data-user-id]") : null;
        if (!userIdElement) {
            var scriptTag = document.querySelector('script[src*="messages.js"]');
            if (scriptTag && scriptTag.dataset.userId) {
                currentUserId = Number(scriptTag.dataset.userId);
            }
        } else {
            currentUserId = Number(userIdElement.dataset.userId || "0");
        }

        attachConversationListeners();

        var newMessageBtn = document.getElementById("sendNewMessageBtn");
        var newMessageForm = document.getElementById("newMessageForm");
        var newMessageModal = document.getElementById("newMessageModal");
        if (newMessageBtn && newMessageForm) {
            newMessageBtn.addEventListener("click", function () {
                var targetInput = document.getElementById("new-message-target");
                var contentInput = document.getElementById("new-message-content");
                var target = targetInput ? targetInput.value.trim() : "";
                var content = contentInput ? contentInput.value.trim() : "";
                if (!target || !content) {
                    if (targetInput) {
                        targetInput.classList.add("is-invalid");
                    }
                    return;
                }
                fetch("/api/messages", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        target: target,
                        content: content,
                    }),
                })
                    .then(function (response) {
                        return response.json();
                    })
                    .then(function (data) {
                        if (data && data.success) {
                            if (newMessageModal) {
                                var modal = bootstrap.Modal.getInstance(newMessageModal);
                                if (modal) {
                                    modal.hide();
                                }
                            }
                            if (newMessageForm) {
                                newMessageForm.reset();
                            }
                            refreshConversationList();
                            setTimeout(function () {
                                var displayName = target;
                                loadConversation(target, displayName);
                            }, 300);
                        } else {
                            var feedback = document.getElementById("target-feedback");
                            if (feedback) {
                                feedback.textContent = data.message || "发送失败，请检查用户名是否正确";
                            }
                            if (targetInput) {
                                targetInput.classList.add("is-invalid");
                            }
                        }
                    })
                    .catch(function (error) {
                        var feedback = document.getElementById("target-feedback");
                        if (feedback) {
                            feedback.textContent = "网络错误，请稍后重试";
                        }
                        if (targetInput) {
                            targetInput.classList.add("is-invalid");
                        }
                    });
            });
        }

        if (newMessageModal) {
            newMessageModal.addEventListener("hidden.bs.modal", function () {
                if (newMessageForm) {
                    newMessageForm.reset();
                }
                var targetInput = document.getElementById("new-message-target");
                if (targetInput) {
                    targetInput.classList.remove("is-invalid");
                }
            });
        }
    });
})();
