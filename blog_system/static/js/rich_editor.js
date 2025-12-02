var BlogEditorSizeConfigurator = (function () {
    var SIZE_OPTIONS = ["10px", "12px", "14px", "16px", "18px", "20px", "22px", "24px", "28px", "32px"];
    function registerSizeAttributor() {
        if (typeof Quill === "undefined") {
            return;
        }
        var SizeStyle = Quill.import("attributors/style/size");
        SizeStyle.whitelist = SIZE_OPTIONS.slice();
        Quill.register(SizeStyle, true);
    }
    function applyOptionsToSelect(selectElement) {
        if (!selectElement || selectElement.getAttribute("data-size-options-initialized") === "true") {
            return;
        }
        while (selectElement.firstChild) {
            selectElement.removeChild(selectElement.firstChild);
        }
        var defaultOption = document.createElement("option");
        defaultOption.textContent = "默认";
        defaultOption.setAttribute("selected", "selected");
        selectElement.appendChild(defaultOption);
        var index;
        for (index = 0; index < SIZE_OPTIONS.length; index += 1) {
            var optionElement = document.createElement("option");
            optionElement.value = SIZE_OPTIONS[index];
            optionElement.textContent = SIZE_OPTIONS[index];
            selectElement.appendChild(optionElement);
        }
        selectElement.setAttribute("data-size-options-initialized", "true");
    }
    function applyToRoot(rootElement) {
        if (!rootElement) {
            return;
        }
        var selects = rootElement.querySelectorAll("select.ql-size");
        var index;
        for (index = 0; index < selects.length; index += 1) {
            applyOptionsToSelect(selects[index]);
        }
    }
    registerSizeAttributor();
    var configurator = {
        applyToRoot: applyToRoot,
        getSizeOptions: function () {
            return SIZE_OPTIONS.slice();
        },
    };
    if (typeof window !== "undefined") {
        window.BlogEditorSizeConfigurator = configurator;
    }
    return configurator;
})();

function BlogEditorModule() {
    this.editorContainer = null;
    this.toolbarContainer = null;
    this.hiddenInput = null;
    this.previewContainer = null;
    this.previewToggle = null;
    this.formElement = null;
    this.quillInstance = null;
}

BlogEditorModule.prototype.initialize = function () {
    this.editorContainer = document.querySelector("#rich-editor");
    this.toolbarContainer = document.querySelector("#rich-editor-toolbar");
    this.hiddenInput = document.querySelector("[data-editor-input]");
    if (!this.editorContainer || !this.toolbarContainer || !this.hiddenInput || typeof Quill === "undefined") {
        return;
    }
    if (BlogEditorSizeConfigurator) {
        BlogEditorSizeConfigurator.applyToRoot(this.toolbarContainer);
    }
    this.previewContainer = document.querySelector("[data-editor-preview]");
    this.previewToggle = document.querySelector("[data-preview-toggle]");
    this.formElement = this.hiddenInput.closest("form");
    this.createQuillInstance();
    this.bindPreviewToggle();
    this.bindFormSubmit();
    this.syncContent();
};

BlogEditorModule.prototype.createQuillInstance = function () {
    var moduleOptions = {
        theme: "snow",
        modules: {
            toolbar: {
                container: this.toolbarContainer,
            },
            history: {
                delay: 500,
                maxStack: 200,
                userOnly: true,
            },
        },
    };
    this.quillInstance = new Quill(this.editorContainer, moduleOptions);
    var toolbarModule = this.quillInstance.getModule("toolbar");
    if (toolbarModule) {
        toolbarModule.addHandler("undo", this.handleUndo.bind(this));
        toolbarModule.addHandler("redo", this.handleRedo.bind(this));
    }
    if (BlogEditorSizeConfigurator && this.toolbarContainer) {
        BlogEditorSizeConfigurator.applyToRoot(this.toolbarContainer);
    }
    if (this.hiddenInput.value) {
        this.quillInstance.root.innerHTML = this.hiddenInput.value;
    }
    this.quillInstance.on("text-change", this.syncContent.bind(this));
};

BlogEditorModule.prototype.handleUndo = function () {
    if (this.quillInstance) {
        this.quillInstance.history.undo();
    }
};

BlogEditorModule.prototype.handleRedo = function () {
    if (this.quillInstance) {
        this.quillInstance.history.redo();
    }
};

BlogEditorModule.prototype.syncContent = function () {
    if (!this.quillInstance || !this.hiddenInput) {
        return;
    }
    var html = this.quillInstance.root.innerHTML.trim();
    this.hiddenInput.value = html;
    if (this.previewContainer) {
        if (html) {
            this.previewContainer.innerHTML = html;
        } else {
            this.previewContainer.innerHTML = '<p class="text-muted mb-0">开始输入内容后，可在此查看最终效果。</p>';
        }
    }
};

BlogEditorModule.prototype.bindPreviewToggle = function () {
    if (!this.previewToggle || !this.previewContainer) {
        return;
    }
    var module = this;
    this.previewToggle.addEventListener("click", function () {
        module.previewContainer.classList.toggle("d-none");
        if (module.previewContainer.classList.contains("d-none")) {
            module.previewToggle.textContent = "显示预览";
        } else {
            module.previewToggle.textContent = "隐藏预览";
            module.syncContent();
        }
    });
};

BlogEditorModule.prototype.bindFormSubmit = function () {
    if (!this.formElement) {
        return;
    }
    var module = this;
    this.formElement.addEventListener("submit", function () {
        module.syncContent();
    });
};

BlogEditorModule.prototype.getHtml = function () {
    if (!this.quillInstance) {
        return "";
    }
    return this.quillInstance.root.innerHTML.trim();
};

BlogEditorModule.prototype.setHtml = function (html) {
    if (!this.quillInstance) {
        return;
    }
    this.quillInstance.root.innerHTML = html || "";
    this.syncContent();
};

BlogEditorModule.prototype.focus = function () {
    if (this.quillInstance) {
        this.quillInstance.focus();
    }
};

function initializeBlogEditorModule() {
    var module = new BlogEditorModule();
    module.initialize();
    window.BlogRichEditor = {
        getHTML: function () {
            return module.getHtml();
        },
        setHTML: function (html) {
            module.setHtml(html);
        },
        focus: function () {
            module.focus();
        },
        sync: function () {
            module.syncContent();
        },
        getQuill: function () {
            return module.quillInstance;
        },
    };
}

document.addEventListener("DOMContentLoaded", initializeBlogEditorModule);
