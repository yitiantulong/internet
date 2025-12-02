(() => {
    function surroundSelection(input, prefix, suffix = prefix) {
        const start = input.selectionStart ?? 0;
        const end = input.selectionEnd ?? 0;
        const value = input.value;
        const selected = value.slice(start, end) || "文本";
        const replacement = `${prefix}${selected}${suffix}`;
        input.setRangeText(replacement, start, end, "end");
        input.focus();
    }

    function insertLinePrefix(input, prefix) {
        const start = input.selectionStart ?? 0;
        const end = input.selectionEnd ?? 0;
        const value = input.value;
        const before = value.slice(0, start);
        const selection = value.slice(start, end);
        const after = value.slice(end);
        const lines = selection || "列表项";
        const formatted = lines
            .split("\n")
            .map((line) => (line ? `${prefix}${line}` : prefix))
            .join("\n");
        input.value = `${before}${formatted}${after}`;
        input.setSelectionRange(before.length, before.length + formatted.length);
        input.focus();
    }

    function promptForLink(input) {
        const url = window.prompt("请输入链接地址（URL）：", "https://");
        if (!url) {
            return;
        }
        surroundSelection(input, "[", `](${url})`);
    }

    document.addEventListener("DOMContentLoaded", () => {
        const target = document.querySelector("[data-editor-target]");
        if (!target) {
            return;
        }
        document.querySelectorAll("[data-editor-action]").forEach((button) => {
            button.addEventListener("click", () => {
                const action = button.getAttribute("data-editor-action");
                switch (action) {
                    case "bold":
                        surroundSelection(target, "**");
                        break;
                    case "italic":
                        surroundSelection(target, "_");
                        break;
                    case "heading":
                        insertLinePrefix(target, "## ");
                        break;
                    case "quote":
                        insertLinePrefix(target, "> ");
                        break;
                    case "code":
                        surroundSelection(target, "`");
                        break;
                    case "list":
                        insertLinePrefix(target, "- ");
                        break;
                    case "link":
                        promptForLink(target);
                        break;
                    default:
                        break;
                }
            });
        });
    });
})();

