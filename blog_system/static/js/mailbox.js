(function () {
    var currentUserId = null;
    var currentView = "inbox";

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

    function formatTimestamp(timestamp) {
        if (!timestamp) return "";
        try {
            var date = new Date(timestamp.replace(" ", "T"));
            return date.toLocaleString("zh-CN");
        } catch (e) {
            return timestamp;
        }
    }

    function loadView(view) {
        currentView = view;
        var content = document.getElementById("mailboxContent");
        if (!content) return;
        content.innerHTML = '<div class="text-center text-muted py-4"><i class="fa-solid fa-spinner fa-spin"></i> 加载中...</div>';

        document.querySelectorAll("[data-view]").forEach(function (item) {
            if (item.getAttribute("data-view") === view) {
                item.classList.add("active");
            } else {
                item.classList.remove("active");
            }
        });

        if (view === "inbox") {
            loadInbox();
        } else if (view === "compose") {
            loadCompose();
        } else if (view === "sent") {
            loadSent();
        } else if (view === "trash") {
            loadTrash();
        }
    }

    function loadInbox() {
        fetch("/api/messages/inbox")
            .then(function (response) {
                if (!response.ok) throw new Error("加载失败");
                return response.json();
            })
            .then(function (data) {
                if (!data || !data.success) {
                    throw new Error(data.message || "加载失败");
                }
                var messages = data.messages || [];
                var html = '<h3 class="h5 mb-3"><i class="fa-solid fa-inbox me-2"></i>收信箱</h3>';
                if (messages.length === 0) {
                    html += '<div class="alert alert-light" role="alert">收信箱为空</div>';
                } else {
                    html += '<div class="list-group" id="inboxMessages">';
                    messages.forEach(function (msg) {
                        var sender = msg.sender || {};
                        var displayName = escapeHTML(sender.display_name || sender.username || "未知");
                        var preview = escapeHTML((msg.content || "").substring(0, 50));
                        var time = formatTimestamp(msg.created_at);
                        var msgId = escapeHTML(msg.id);
                        html += '<div class="list-group-item" data-message-id="' + msgId + '">' +
                            '<div class="d-flex justify-content-between align-items-start">' +
                            '<div class="flex-grow-1">' +
                            '<h6 class="mb-1">' + displayName + '</h6>' +
                            '<p class="mb-1 text-muted">' + preview + '</p>' +
                            '<small class="text-muted">' + time + '</small>' +
                            '</div>' +
                            '<div class="d-flex gap-2">' +
                            '<button class="btn btn-sm btn-outline-primary view-message-btn" data-message-id="' + msgId + '">查看</button>' +
                            '<button class="btn btn-sm btn-outline-danger delete-message-btn" data-message-id="' + msgId + '">删除</button>' +
                            '</div>' +
                            '</div>' +
                            '</div>';
                    });
                    html += '</div>';
                    document.getElementById("mailboxContent").innerHTML = html;
                    document.querySelectorAll(".view-message-btn").forEach(function (btn) {
                        btn.addEventListener("click", function () {
                            viewMessage(this.getAttribute("data-message-id"));
                        });
                    });
                    document.querySelectorAll(".delete-message-btn").forEach(function (btn) {
                        btn.addEventListener("click", function () {
                            deleteMessage(this.getAttribute("data-message-id"));
                        });
                    });
                    return;
                }
                document.getElementById("mailboxContent").innerHTML = html;
            })
            .catch(function (error) {
                document.getElementById("mailboxContent").innerHTML =
                    '<div class="alert alert-danger" role="alert">' + escapeHTML(error.message) + "</div>";
            });
    }

    function loadCompose() {
        var content = document.getElementById("mailboxContent");
        var receiver = content ? (content.dataset.receiver || "") : "";
        var html = '<h3 class="h5 mb-3"><i class="fa-regular fa-pen-to-square me-2"></i>发送信件</h3>' +
            '<form id="composeForm">' +
            '<div class="mb-3">' +
            '<label for="receiver" class="form-label">收信人用户名</label>' +
            '<input type="text" class="form-control" id="receiver" name="receiver" required placeholder="输入收信人用户名" value="' + escapeHTML(receiver) + '">' +
            '<div class="invalid-feedback" id="receiver-feedback"></div>' +
            '</div>' +
            '<div class="mb-3">' +
            '<label for="content" class="form-label">信件内容</label>' +
            '<textarea class="form-control" id="content" name="content" rows="10" required placeholder="输入信件内容..."></textarea>' +
            '</div>' +
            '<button type="submit" class="btn btn-primary">' +
            '<i class="fa-solid fa-paper-plane-top me-1"></i>发送</button>' +
            '</form>';
        document.getElementById("mailboxContent").innerHTML = html;
        document.getElementById("composeForm").addEventListener("submit", function (e) {
            e.preventDefault();
            sendMessage();
        });
    }

    function sendMessage() {
        var receiver = document.getElementById("receiver").value.trim();
        var content = document.getElementById("content").value.trim();
        if (!receiver || !content) {
            alert("请填写收信人和内容");
            return;
        }
        fetch("/api/messages", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target: receiver, content: content }),
        })
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                if (data && data.success) {
                    alert("发送成功！");
                    document.getElementById("composeForm").reset();
                    window.history.pushState({}, "", "/messages?view=sent");
                    loadView("sent");
                } else {
                    var feedback = document.getElementById("receiver-feedback");
                    if (feedback) {
                        feedback.textContent = data.message || "发送失败，请检查用户名是否正确";
                    }
                    document.getElementById("receiver").classList.add("is-invalid");
                }
            })
            .catch(function (error) {
                alert("发送失败：" + error.message);
            });
    }

    function loadSent() {
        fetch("/api/messages/sent")
            .then(function (response) {
                if (!response.ok) throw new Error("加载失败");
                return response.json();
            })
            .then(function (data) {
                if (!data || !data.success) {
                    throw new Error(data.message || "加载失败");
                }
                var messages = data.messages || [];
                var html = '<h3 class="h5 mb-3"><i class="fa-solid fa-paper-plane me-2"></i>已发送</h3>';
                if (messages.length === 0) {
                    html += '<div class="alert alert-light" role="alert">暂无已发送的信件</div>';
                } else {
                    html += '<div class="list-group" id="sentMessages">';
                    messages.forEach(function (msg) {
                        var receiver = msg.receiver || {};
                        var displayName = escapeHTML(receiver.display_name || receiver.username || "未知");
                        var preview = escapeHTML((msg.content || "").substring(0, 50));
                        var time = formatTimestamp(msg.created_at);
                        var msgId = escapeHTML(msg.id);
                        html += '<div class="list-group-item" data-message-id="' + msgId + '">' +
                            '<div class="d-flex justify-content-between align-items-start">' +
                            '<div class="flex-grow-1">' +
                            '<h6 class="mb-1">收信人：' + displayName + '</h6>' +
                            '<p class="mb-1 text-muted">' + preview + '</p>' +
                            '<small class="text-muted">' + time + '</small>' +
                            '</div>' +
                            '<div class="d-flex gap-2">' +
                            '<button class="btn btn-sm btn-outline-primary view-message-btn" data-message-id="' + msgId + '">查看</button>' +
                            '<button class="btn btn-sm btn-outline-danger delete-message-btn" data-message-id="' + msgId + '">删除</button>' +
                            '</div>' +
                            '</div>' +
                            '</div>';
                    });
                    html += '</div>';
                    document.getElementById("mailboxContent").innerHTML = html;
                    document.querySelectorAll(".view-message-btn").forEach(function (btn) {
                        btn.addEventListener("click", function () {
                            viewMessage(this.getAttribute("data-message-id"));
                        });
                    });
                    document.querySelectorAll(".delete-message-btn").forEach(function (btn) {
                        btn.addEventListener("click", function () {
                            deleteMessage(this.getAttribute("data-message-id"));
                        });
                    });
                    return;
                }
                document.getElementById("mailboxContent").innerHTML = html;
            })
            .catch(function (error) {
                document.getElementById("mailboxContent").innerHTML =
                    '<div class="alert alert-danger" role="alert">' + escapeHTML(error.message) + "</div>";
            });
    }

    function loadTrash() {
        fetch("/api/messages/trash")
            .then(function (response) {
                if (!response.ok) throw new Error("加载失败");
                return response.json();
            })
            .then(function (data) {
                if (!data || !data.success) {
                    throw new Error(data.message || "加载失败");
                }
                var messages = data.messages || [];
                var html = '<h3 class="h5 mb-3"><i class="fa-solid fa-trash me-2"></i>垃圾箱</h3>';
                if (messages.length === 0) {
                    html += '<div class="alert alert-light" role="alert">垃圾箱为空</div>';
                } else {
                    html += '<div class="list-group" id="trashMessages">';
                    messages.forEach(function (msg) {
                        var other = msg.other_user || {};
                        var displayName = escapeHTML(other.display_name || other.username || "未知");
                        var preview = escapeHTML((msg.content || "").substring(0, 50));
                        var time = formatTimestamp(msg.created_at);
                        var msgId = escapeHTML(msg.id);
                        html += '<div class="list-group-item" data-message-id="' + msgId + '">' +
                            '<div class="d-flex justify-content-between align-items-start">' +
                            '<div class="flex-grow-1">' +
                            '<h6 class="mb-1">' + (msg.is_sender ? "发送给" : "来自") + "：" + displayName + '</h6>' +
                            '<p class="mb-1 text-muted">' + preview + '</p>' +
                            '<small class="text-muted">' + time + '</small>' +
                            '</div>' +
                            '<div class="d-flex gap-2">' +
                            '<button class="btn btn-sm btn-outline-success restore-message-btn" data-message-id="' + msgId + '">恢复</button>' +
                            '<button class="btn btn-sm btn-outline-danger permanent-delete-message-btn" data-message-id="' + msgId + '">彻底删除</button>' +
                            '</div>' +
                            '</div>' +
                            '</div>';
                    });
                    html += '</div>';
                    document.getElementById("mailboxContent").innerHTML = html;
                    document.querySelectorAll(".restore-message-btn").forEach(function (btn) {
                        btn.addEventListener("click", function () {
                            restoreMessage(this.getAttribute("data-message-id"));
                        });
                    });
                    document.querySelectorAll(".permanent-delete-message-btn").forEach(function (btn) {
                        btn.addEventListener("click", function () {
                            permanentlyDeleteMessage(this.getAttribute("data-message-id"));
                        });
                    });
                    return;
                }
                document.getElementById("mailboxContent").innerHTML = html;
            })
            .catch(function (error) {
                document.getElementById("mailboxContent").innerHTML =
                    '<div class="alert alert-danger" role="alert">' + escapeHTML(error.message) + "</div>";
            });
    }

    window.viewMessage = function (messageId) {
        fetch("/api/messages/" + encodeURIComponent(messageId))
            .then(function (response) {
                if (!response.ok) throw new Error("加载失败");
                return response.json();
            })
            .then(function (data) {
                if (!data || !data.success) {
                    throw new Error(data.message || "加载失败");
                }
                var msg = data.message;
                var sender = msg.sender || {};
                var receiver = msg.receiver || {};
                var modal = new bootstrap.Modal(document.createElement("div"));
                var modalHtml = '<div class="modal fade" id="messageModal" tabindex="-1">' +
                    '<div class="modal-dialog modal-lg">' +
                    '<div class="modal-content">' +
                    '<div class="modal-header">' +
                    '<h5 class="modal-title">信件详情</h5>' +
                    '<button type="button" class="btn-close" data-bs-dismiss="modal"></button>' +
                    '</div>' +
                    '<div class="modal-body">' +
                    '<p><strong>发信人：</strong>' + escapeHTML(sender.display_name || sender.username) + '</p>' +
                    '<p><strong>收信人：</strong>' + escapeHTML(receiver.display_name || receiver.username) + '</p>' +
                    '<p><strong>时间：</strong>' + formatTimestamp(msg.created_at) + '</p>' +
                    '<hr>' +
                    '<div class="message-content">' + escapeHTML(msg.content).replace(/\n/g, "<br>") + '</div>' +
                    '</div>' +
                    '</div>' +
                    '</div>' +
                    '</div>';
                document.body.insertAdjacentHTML("beforeend", modalHtml);
                var modalEl = document.getElementById("messageModal");
                var bsModal = new bootstrap.Modal(modalEl);
                bsModal.show();
                modalEl.addEventListener("hidden.bs.modal", function () {
                    modalEl.remove();
                });
            })
            .catch(function (error) {
                alert("加载失败：" + error.message);
            });
    };

    window.deleteMessage = function (messageId) {
        if (!confirm("确定要删除这条消息吗？")) return;
        fetch("/api/messages/" + encodeURIComponent(messageId) + "/delete", { method: "POST" })
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                if (data && data.success) {
                    alert("已删除");
                    loadView(currentView);
                } else {
                    alert("删除失败：" + (data.message || "未知错误"));
                }
            })
            .catch(function (error) {
                alert("删除失败：" + error.message);
            });
    };

    window.restoreMessage = function (messageId) {
        fetch("/api/messages/" + encodeURIComponent(messageId) + "/restore", { method: "POST" })
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                if (data && data.success) {
                    alert("已恢复");
                    loadView("trash");
                } else {
                    alert("恢复失败：" + (data.message || "未知错误"));
                }
            })
            .catch(function (error) {
                alert("恢复失败：" + error.message);
            });
    };

    window.permanentlyDeleteMessage = function (messageId) {
        if (!confirm("确定要彻底删除这条消息吗？此操作不可恢复！")) return;
        fetch("/api/messages/" + encodeURIComponent(messageId) + "/permanent-delete", { method: "POST" })
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                if (data && data.success) {
                    alert("已彻底删除");
                    loadView("trash");
                } else {
                    alert("删除失败：" + (data.message || "未知错误"));
                }
            })
            .catch(function (error) {
                alert("删除失败：" + error.message);
            });
    };

    document.addEventListener("DOMContentLoaded", function () {
        var content = document.getElementById("mailboxContent");
        if (content) {
            currentUserId = Number(content.dataset.userId || "0");
        }
        var urlParams = new URLSearchParams(window.location.search);
        var view = urlParams.get("view") || "inbox";
        loadView(view);
        document.querySelectorAll("[data-view]").forEach(function (item) {
            item.addEventListener("click", function (e) {
                e.preventDefault();
                var view = this.getAttribute("data-view");
                window.history.pushState({}, "", "/messages?view=" + view);
                loadView(view);
            });
        });
    });
})();

