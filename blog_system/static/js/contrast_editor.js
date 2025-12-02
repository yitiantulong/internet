function ContrastEditorUtilities() {
}

ContrastEditorUtilities.prototype.extractPlainText = function (html) {
    if (!html) {
        return "";
    }
    var parser = new DOMParser();
    var doc = parser.parseFromString(html, "text/html");
    return doc.body.textContent || "";
};

ContrastEditorUtilities.prototype.createSanitizedHtml = function (html, customConfig) {
    if (typeof DOMPurify === "undefined") {
        return html;
    }
    var baseConfig = {
        ALLOW_ARIA_ATTR: true,
        ALLOW_DATA_ATTR: true,
        ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel|ftp):|[^a-z]|[a-z+.-]+(?:[^a-z]|$))/i,
        ADD_TAGS: [
            "section",
            "article",
            "header",
            "footer",
            "figure",
            "figcaption",
            "picture",
            "source",
            "video",
            "audio",
            "span",
            "div",
            "u",
            "s",
            "sub",
            "sup",
        ],
        ADD_ATTR: [
            "style",
            "class",
            "id",
            "target",
            "rel",
            "aria-label",
            "aria-hidden",
        ],
    };
    if (customConfig && typeof customConfig === "object") {
        Object.keys(customConfig).forEach(function (key) {
            baseConfig[key] = customConfig[key];
        });
    }
    return DOMPurify.sanitize(html, baseConfig);
};

ContrastEditorUtilities.prototype.isMeaningfulHtml = function (html) {
    if (!html) {
        return false;
    }
    var normalized = html
        .replace(/<p><br\s*\/?><\/p>/gi, "")
        .replace(/&nbsp;/gi, " ");
    var textContent = this.extractPlainText(normalized);
    return Boolean(textContent && textContent.trim().length > 0);
};

ContrastEditorUtilities.prototype.convertLatexToHtml = function (content) {
    if (typeof katex === "undefined" || !content) {
        return '<div class="latex-preview-empty text-muted">在此输入 LaTeX 内容以渲染公式。</div>';
    }
    try {
        var rendered = katex.renderToString(content, {
            throwOnError: false,
            displayMode: true,
        });
        return this.createSanitizedHtml(rendered);
    } catch (error) {
        var safeMessage = this.createSanitizedHtml(String(error));
        return '<div class="latex-preview-error text-danger">渲染失败：' + safeMessage + "</div>";
    }
};

ContrastEditorUtilities.prototype.convertMarkdownToHtml = function (content) {
    if (typeof marked === "undefined" || !content) {
        return '<p class="text-muted mb-0">输入 Markdown 内容即可实时预览。</p>';
    }
    var rendered = marked.parse(content, { breaks: true });
    return this.createSanitizedHtml(rendered);
};

function ContrastEditorInitializer() {
    this.utilities = new ContrastEditorUtilities();
}

ContrastEditorInitializer.prototype.run = function () {
    var openButton = document.querySelector("[data-contrast-open]");
    var templateElement = document.getElementById("contrast-editor-template");
    var mountElement = document.getElementById("contrastEditorApp");
    if (!openButton || !templateElement || !mountElement) {
        return;
    }
    if (typeof Vue === "undefined" || typeof Quill === "undefined" || typeof CodeMirror === "undefined") {
        return;
    }
    var app = this.createVueApp(templateElement.innerHTML);
    var vm = app.mount(mountElement);
    openButton.addEventListener("click", function () {
        vm.openModal();
    });
};

ContrastEditorInitializer.prototype.createVueApp = function (templateHtml) {
    var utilities = this.utilities;
    var EMPTY_PREVIEW_HTML = '<p class="text-muted mb-0">开始创作内容即可预览。</p>';

    return Vue.createApp({
        template: templateHtml,
        data: function () {
            return {
                visible: false,
                activeMode: "word",
                leftPercent: 50,
                isDragging: false,
                dragStartX: 0,
                initialLeftPercent: 50,
                previewHtml: EMPTY_PREVIEW_HTML,
                isSyncingScroll: false,
                initialLoad: false,
                wordEditorInstance: null,
                markdownEditorInstance: null,
                latexEditorInstance: null,
                wordScrollElement: null,
                markdownScrollElement: null,
                latexScrollElement: null,
                wordScrollHandler: null,
                markdownScrollHandler: null,
                latexScrollHandler: null,
                previewScrollHandler: null,
                wordTextChangeHandler: null,
                markdownChangeHandler: null,
                latexChangeHandler: null,
            };
        },
        computed: {
            leftPaneStyle: function () {
                return { width: this.leftPercent + "%" };
            },
            rightPaneStyle: function () {
                return { width: 100 - this.leftPercent + "%" };
            },
            modalClassList: function () {
                return { "contrast-editor-visible": this.visible };
            },
        },
        methods: {
            openModal: function () {
                this.visible = true;
                this.initialLoad = true;
                this.activeMode = "word";
                this.previewHtml = EMPTY_PREVIEW_HTML;
                this.leftPercent = 50;
                var component = this;
                this.$nextTick(function () {
                    component.ensurePreviewPaneListener();
                    component.initializeCurrentEditor(true);
                });
            },
            closeModal: function () {
                this.applyToMainEditor();
                this.destroyAllEditors();
                this.visible = false;
                this.previewHtml = EMPTY_PREVIEW_HTML;
            },
            ensurePreviewPaneListener: function () {
                if (this.previewScrollHandler || !this.$refs.previewPane) {
                    return;
                }
                this.previewScrollHandler = this.handlePreviewScroll.bind(this);
                this.$refs.previewPane.addEventListener("scroll", this.previewScrollHandler);
            },
            initializeCurrentEditor: function (loadFromMain) {
                if (this.activeMode === "word") {
                    this.createWordEditor(loadFromMain);
                } else if (this.activeMode === "markdown") {
                    this.createMarkdownEditor();
                } else {
                    this.createLatexEditor();
                }
                this.renderPreview();
                this.focusActiveEditor();
                this.initialLoad = false;
            },
            destroyEditorByMode: function (mode) {
                if (mode === "word") {
                    this.destroyWordEditor();
                } else if (mode === "markdown") {
                    this.destroyMarkdownEditor();
                } else if (mode === "latex") {
                    this.destroyLatexEditor();
                }
            },
            destroyAllEditors: function () {
                this.destroyWordEditor();
                this.destroyMarkdownEditor();
                this.destroyLatexEditor();
                if (this.previewScrollHandler && this.$refs.previewPane) {
                    this.$refs.previewPane.removeEventListener("scroll", this.previewScrollHandler);
                    this.previewScrollHandler = null;
                }
            },
            createWordEditor: function (loadFromMain) {
                this.destroyWordEditor();
                var editorElement = this.$refs.wordEditor;
                var toolbarElement = this.$refs.wordToolbar;
                if (!editorElement || !toolbarElement) {
                    return;
                }
                if (typeof BlogEditorSizeConfigurator !== "undefined") {
                    BlogEditorSizeConfigurator.applyToRoot(toolbarElement);
                }
                var component = this;
                this.wordEditorInstance = new Quill(editorElement, {
                    theme: "snow",
                    modules: {
                        toolbar: {
                            container: toolbarElement,
                            handlers: {
                                undo: function () {
                                    component.wordEditorInstance.history.undo();
                                },
                                redo: function () {
                                    component.wordEditorInstance.history.redo();
                                },
                            },
                        },
                        history: {
                            delay: 500,
                            maxStack: 200,
                            userOnly: true,
                        },
                    },
                });
                this.wordTextChangeHandler = function () {
                    component.renderPreview();
                };
                this.wordEditorInstance.on("text-change", this.wordTextChangeHandler);
                if (loadFromMain && this.initialLoad) {
                    var html = this.obtainInitialHtml();
                    if (html) {
                        var safeHtml = utilities.createSanitizedHtml(html);
                        this.wordEditorInstance.root.innerHTML = safeHtml;
                    }
                } else {
                    this.wordEditorInstance.root.innerHTML = "";
                }
                this.wordScrollElement = this.wordEditorInstance.root;
                this.wordScrollHandler = function () {
                    component.syncScroll(component.wordScrollElement);
                };
                this.wordScrollElement.addEventListener("scroll", this.wordScrollHandler);
            },
            destroyWordEditor: function () {
                if (this.wordEditorInstance && this.wordTextChangeHandler) {
                    this.wordEditorInstance.off("text-change", this.wordTextChangeHandler);
                }
                if (this.wordScrollElement && this.wordScrollHandler) {
                    this.wordScrollElement.removeEventListener("scroll", this.wordScrollHandler);
                }
                if (this.$refs.wordEditor) {
                    this.$refs.wordEditor.innerHTML = "";
                }
                this.wordEditorInstance = null;
                this.wordScrollElement = null;
                this.wordScrollHandler = null;
                this.wordTextChangeHandler = null;
            },
            createMarkdownEditor: function () {
                this.destroyMarkdownEditor();
                var markdownArea = this.$refs.markdownEditor;
                if (!markdownArea) {
                    return;
                }
                var component = this;
                this.markdownEditorInstance = CodeMirror.fromTextArea(markdownArea, {
                    mode: "markdown",
                    lineNumbers: true,
                    lineWrapping: true,
                });
                this.markdownEditorInstance.setValue("");
                this.markdownChangeHandler = function () {
                    component.renderPreview();
                };
                this.markdownEditorInstance.on("change", this.markdownChangeHandler);
                this.markdownScrollElement = this.markdownEditorInstance.getScrollerElement();
                this.markdownScrollHandler = function () {
                    component.syncScroll(component.markdownScrollElement);
                };
                this.markdownScrollElement.addEventListener("scroll", this.markdownScrollHandler);
            },
            destroyMarkdownEditor: function () {
                if (this.markdownEditorInstance && this.markdownChangeHandler) {
                    this.markdownEditorInstance.off("change", this.markdownChangeHandler);
                }
                if (this.markdownScrollElement && this.markdownScrollHandler) {
                    this.markdownScrollElement.removeEventListener("scroll", this.markdownScrollHandler);
                }
                if (this.markdownEditorInstance) {
                    this.markdownEditorInstance.toTextArea();
                }
                this.markdownEditorInstance = null;
                this.markdownScrollElement = null;
                this.markdownScrollHandler = null;
                this.markdownChangeHandler = null;
            },
            createLatexEditor: function () {
                this.destroyLatexEditor();
                var latexArea = this.$refs.latexEditor;
                if (!latexArea) {
                    return;
                }
                var component = this;
                this.latexEditorInstance = CodeMirror.fromTextArea(latexArea, {
                    mode: "stex",
                    lineNumbers: true,
                    lineWrapping: true,
                });
                this.latexEditorInstance.setValue("");
                this.latexChangeHandler = function () {
                    component.renderPreview();
                };
                this.latexEditorInstance.on("change", this.latexChangeHandler);
                this.latexScrollElement = this.latexEditorInstance.getScrollerElement();
                this.latexScrollHandler = function () {
                    component.syncScroll(component.latexScrollElement);
                };
                this.latexScrollElement.addEventListener("scroll", this.latexScrollHandler);
            },
            destroyLatexEditor: function () {
                if (this.latexEditorInstance && this.latexChangeHandler) {
                    this.latexEditorInstance.off("change", this.latexChangeHandler);
                }
                if (this.latexScrollElement && this.latexScrollHandler) {
                    this.latexScrollElement.removeEventListener("scroll", this.latexScrollHandler);
                }
                if (this.latexEditorInstance) {
                    this.latexEditorInstance.toTextArea();
                }
                this.latexEditorInstance = null;
                this.latexScrollElement = null;
                this.latexScrollHandler = null;
                this.latexChangeHandler = null;
            },
            switchMode: function (mode) {
                if (mode === this.activeMode) {
                    return;
                }
                var previousMode = this.activeMode;
                this.destroyEditorByMode(previousMode);
                this.activeMode = mode;
                this.previewHtml = EMPTY_PREVIEW_HTML;
                var component = this;
                this.$nextTick(function () {
                    component.initializeCurrentEditor(false);
                });
            },
            obtainInitialHtml: function () {
                if (window.BlogRichEditor && typeof window.BlogRichEditor.getHTML === "function") {
                    return window.BlogRichEditor.getHTML();
                }
                return "";
            },
            applyToMainEditor: function () {
                if (!window.BlogRichEditor || typeof window.BlogRichEditor.setHTML !== "function") {
                    return;
                }
                window.BlogRichEditor.setHTML(this.previewHtml === EMPTY_PREVIEW_HTML ? "" : this.previewHtml);
            },
            focusActiveEditor: function () {
                if (this.activeMode === "word" && this.wordEditorInstance) {
                    this.wordEditorInstance.focus();
                } else if (this.activeMode === "markdown" && this.markdownEditorInstance) {
                    this.markdownEditorInstance.focus();
                } else if (this.activeMode === "latex" && this.latexEditorInstance) {
                    this.latexEditorInstance.focus();
                }
            },
            renderPreview: function () {
                var html = "";
                if (this.activeMode === "word" && this.wordEditorInstance) {
                    var rawHtml = this.wordEditorInstance.root.innerHTML;
                    html = utilities.createSanitizedHtml(rawHtml);
                } else if (this.activeMode === "markdown" && this.markdownEditorInstance) {
                    html = utilities.convertMarkdownToHtml(this.markdownEditorInstance.getValue());
                } else if (this.activeMode === "latex" && this.latexEditorInstance) {
                    html = utilities.convertLatexToHtml(this.latexEditorInstance.getValue());
                }
                if (!utilities.isMeaningfulHtml(html)) {
                    html = EMPTY_PREVIEW_HTML;
                }
                this.previewHtml = html;
                if (this.activeMode === "latex") {
                    this.$nextTick(this.renderMathPreview);
                }
            },
            renderMathPreview: function () {
                if (typeof renderMathInElement !== "function") {
                    return;
                }
                var previewElement = this.$refs.previewContent;
                if (!previewElement) {
                    return;
                }
                renderMathInElement(previewElement, {
                    delimiters: [
                        { left: "$$", right: "$$", display: true },
                        { left: "\\(", right: "\\)", display: false },
                    ],
                    throwOnError: false,
                });
            },
            syncScroll: function (sourceElement) {
                if (!sourceElement || !this.$refs.previewPane) {
                    return;
                }
                if (this.isSyncingScroll) {
                    return;
                }
                this.isSyncingScroll = true;
                var sourceScrollable = sourceElement.scrollHeight - sourceElement.clientHeight;
                var ratio = 0;
                if (sourceScrollable > 0) {
                    ratio = sourceElement.scrollTop / sourceScrollable;
                }
                var previewElement = this.$refs.previewPane;
                var previewScrollable = previewElement.scrollHeight - previewElement.clientHeight;
                previewElement.scrollTop = ratio * previewScrollable;
                this.isSyncingScroll = false;
            },
            handlePreviewScroll: function (event) {
                if (this.isSyncingScroll) {
                    return;
                }
                this.isSyncingScroll = true;
                var previewElement = event.target;
                var previewScrollable = previewElement.scrollHeight - previewElement.clientHeight;
                var ratio = 0;
                if (previewScrollable > 0) {
                    ratio = previewElement.scrollTop / previewScrollable;
                }
                this.syncActiveEditorScroll(ratio);
                this.isSyncingScroll = false;
            },
            syncActiveEditorScroll: function (ratio) {
                var editorElement = null;
                if (this.activeMode === "word" && this.wordScrollElement) {
                    editorElement = this.wordScrollElement;
                } else if (this.activeMode === "markdown" && this.markdownScrollElement) {
                    editorElement = this.markdownScrollElement;
                } else if (this.activeMode === "latex" && this.latexScrollElement) {
                    editorElement = this.latexScrollElement;
                }
                if (!editorElement) {
                    return;
                }
                var scrollable = editorElement.scrollHeight - editorElement.clientHeight;
                editorElement.scrollTop = ratio * scrollable;
            },
            startDrag: function (event) {
                this.isDragging = true;
                this.dragStartX = event.clientX;
                this.initialLeftPercent = this.leftPercent;
            },
            handleDragMove: function (event) {
                if (!this.isDragging) {
                    return;
                }
                var container = this.$refs.modalBody;
                if (!container) {
                    return;
                }
                var width = container.clientWidth;
                if (width <= 0) {
                    return;
                }
                var delta = event.clientX - this.dragStartX;
                var percentDelta = (delta / width) * 100;
                var nextPercent = this.initialLeftPercent + percentDelta;
                if (nextPercent < 25) {
                    nextPercent = 25;
                } else if (nextPercent > 75) {
                    nextPercent = 75;
                }
                this.leftPercent = nextPercent;
            },
            handleDragEnd: function () {
                this.isDragging = false;
            },
        },
        watch: {
            activeMode: function () {
                this.renderPreview();
            },
        },
        mounted: function () {
            window.addEventListener("mousemove", this.handleDragMove);
            window.addEventListener("mouseup", this.handleDragEnd);
        },
        beforeUnmount: function () {
            window.removeEventListener("mousemove", this.handleDragMove);
            window.removeEventListener("mouseup", this.handleDragEnd);
            this.destroyAllEditors();
        },
    });
};

function initializeContrastEditor() {
    var initializer = new ContrastEditorInitializer();
    initializer.run();
}

document.addEventListener("DOMContentLoaded", initializeContrastEditor);

