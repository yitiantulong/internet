function formatTimestampForDownload(dateInstance) {
    var year = dateInstance.getFullYear();
    var month = String(dateInstance.getMonth() + 1).padStart(2, "0");
    var day = String(dateInstance.getDate()).padStart(2, "0");
    var hours = String(dateInstance.getHours()).padStart(2, "0");
    var minutes = String(dateInstance.getMinutes()).padStart(2, "0");
    return "" + year + month + day + hours + minutes;
}

function sanitizeFileTitle(rawTitle) {
    if (!rawTitle) {
        return "文章";
    }
    return rawTitle.replace(/[\\/:*?"<>|]/g, "_").trim() || "文章";
}

function buildDownloadFileName(titleText, extension) {
    var safeTitle = sanitizeFileTitle(titleText);
    var timestamp = formatTimestampForDownload(new Date());
    return safeTitle + "_" + timestamp + "." + extension;
}

function getPostTitleText() {
    var titleElement = document.querySelector(".post-detail h1");
    if (!titleElement) {
        return "文章";
    }
    return titleElement.textContent.trim();
}

function getPostContentElement() {
    return document.querySelector(".post-detail .post-content");
}

function triggerBlobDownload(blobObject, fileName) {
    if (!blobObject) {
        return;
    }
    var url = URL.createObjectURL(blobObject);
    var anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
}

function warnMissingLibrary(libraryName) {
    console.warn("缺少依赖库：" + libraryName + "，无法完成下载。");
}

function setButtonBusyState(buttonElement, isBusy) {
    if (!buttonElement) {
        return;
    }
    if (isBusy) {
        buttonElement.setAttribute("data-busy", "true");
        buttonElement.setAttribute("aria-busy", "true");
        buttonElement.classList.add("disabled");
    } else {
        buttonElement.removeAttribute("data-busy");
        buttonElement.removeAttribute("aria-busy");
        buttonElement.classList.remove("disabled");
    }
}

function downloadPostAsPdf(buttonElement) {
    var contentElement = getPostContentElement();
    if (!contentElement) {
        console.warn("未找到文章内容区域，无法导出 PDF。");
        return;
    }
    if (typeof window.html2canvas !== "function") {
        warnMissingLibrary("html2canvas");
        return;
    }
    if (!window.jspdf || typeof window.jspdf.jsPDF !== "function") {
        warnMissingLibrary("jsPDF");
        return;
    }
    var titleText = getPostTitleText();
    var fileName = buildDownloadFileName(titleText, "pdf");
    var renderOptions = {
        scale: 2,
        useCORS: true,
        backgroundColor: "#ffffff",
        logging: false,
        windowWidth: contentElement.scrollWidth
    };
    function handleCanvasRendered(canvas) {
        try {
            var jsPDFConstructor = window.jspdf.jsPDF;
            var pdf = new jsPDFConstructor("p", "mm", "a4");
            var pageWidth = pdf.internal.pageSize.getWidth();
            var pageHeight = pdf.internal.pageSize.getHeight();
            var imgData = canvas.toDataURL("image/png");
            var imgWidth = pageWidth;
            var imgHeight = canvas.height * imgWidth / canvas.width;
            var position = 0;
            pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
            var heightLeft = imgHeight - pageHeight;
            while (heightLeft > 0) {
                position = heightLeft - imgHeight;
                pdf.addPage();
                pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
                heightLeft -= pageHeight;
            }
            pdf.save(fileName);
        } catch (error) {
            console.error("导出 PDF 时发生错误：", error);
        } finally {
            setButtonBusyState(buttonElement, false);
        }
    }
    function handleCanvasError(error) {
        console.error("生成 PDF 画布失败：", error);
        setButtonBusyState(buttonElement, false);
    }
    setButtonBusyState(buttonElement, true);
    window.html2canvas(contentElement, renderOptions).then(handleCanvasRendered).catch(handleCanvasError);
}

function downloadPostAsDocx(buttonElement) {
    var contentElement = getPostContentElement();
    if (!contentElement) {
        console.warn("未找到文章内容区域，无法导出 Word。");
        return;
    }
    if (!window.htmlDocx || typeof window.htmlDocx.asBlob !== "function") {
        warnMissingLibrary("html-docx-js");
        return;
    }
    var titleText = getPostTitleText();
    var fileName = buildDownloadFileName(titleText, "docx");
    var styleBlock = (
        "<style>" +
        "body{font-family:Arial,'Microsoft YaHei',sans-serif;line-height:1.8;color:#1f2937;}" +
        "table{border-collapse:collapse;width:100%;}" +
        "table td,table th{border:1px solid #d1d5db;padding:8px;}" +
        "</style>"
    );
    var htmlContent = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>" +
        styleBlock +
        "</head><body>" +
        contentElement.innerHTML +
        "</body></html>"
    );
    setButtonBusyState(buttonElement, true);
    try {
        var blobObject = window.htmlDocx.asBlob(htmlContent);
        triggerBlobDownload(blobObject, fileName);
    } catch (error) {
        console.error("导出 Word 时发生错误：", error);
    } finally {
        setButtonBusyState(buttonElement, false);
    }
}

function handleDownloadClick(event) {
    var buttonElement = event.currentTarget;
    if (buttonElement.getAttribute("data-busy") === "true") {
        return;
    }
    var downloadType = buttonElement.getAttribute("data-download-type");
    if (downloadType === "pdf") {
        downloadPostAsPdf(buttonElement);
    } else if (downloadType === "docx") {
        downloadPostAsDocx(buttonElement);
    }
}

function initializeDownloadButtons() {
    var buttons = document.querySelectorAll("[data-download-type]");
    if (!buttons || buttons.length === 0) {
        return;
    }
    for (var index = 0; index < buttons.length; index += 1) {
        var button = buttons[index];
        if (!button) {
            continue;
        }
        button.addEventListener("click", handleDownloadClick);
    }
}

function handleContentLoaded() {
    initializeDownloadButtons();
}

document.addEventListener("DOMContentLoaded", handleContentLoaded);

