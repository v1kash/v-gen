const MODE_IMAGE = "image";
const MODE_VIDEO = "video";
const MODE_AI_VIDEO = "ai-video";

const state = {
    mode: MODE_IMAGE,
    videoEngine: "manim",
    aiVideoMode: "text",
    loading: false,
};

// Rough estimated generation times (seconds) used to animate a progress bar client-side.
// The backend runs to completion before responding, so this is an estimate, not live progress.
const ESTIMATED_LOAD_SECONDS = {
    [MODE_IMAGE]: 60, // SDXL, 30 steps ≈ 25s on GPU + load time
    [MODE_VIDEO]: 180, // Manim render can take a couple of minutes
    [MODE_AI_VIDEO]: 600,
};

let progressTimer = null;
let zoomLevel = 1;
let historyItems = [];
let historyType = MODE_IMAGE;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3;
const ZOOM_STEP = 0.25;
let fittedImageSize = null;

function setMode(mode) {
    state.mode = mode;
    document.getElementById("mode-image").classList.toggle("active", mode === MODE_IMAGE);
    document.getElementById("mode-video").classList.toggle("active", mode === MODE_VIDEO);
    document.getElementById("mode-title").textContent = mode === MODE_IMAGE
        ? "Generate image from prompt"
        : "Generate video from prompt";

    const img = document.getElementById("generated-image");
    const video = document.getElementById("animation");
    const showImage = mode === MODE_IMAGE && img.hasAttribute("src");
    const showVideo = mode === MODE_VIDEO && video.hasAttribute("src");
    document.getElementById("image-settings").style.display = mode === MODE_IMAGE ? "flex" : "none";
    document.getElementById("video-controls").style.display = mode === MODE_VIDEO ? "flex" : "none";
    updateAiVideoControls();
    document.getElementById("viewer-shell").style.display = showImage || showVideo ? "block" : "none";
    document.getElementById("viewer-controls").style.display = showImage || showVideo ? "flex" : "none";
    document.getElementById("media-stage").style.display = showImage || showVideo ? "block" : "none";
    document.getElementById("image-canvas").style.display = showImage ? "grid" : "none";
    img.style.display = showImage ? "block" : "none";
    video.style.display = showVideo ? "block" : "none";
    document.getElementById("zoom-controls").style.display = showImage ? "flex" : "none";
    if (showImage) setViewerPrompt(promptForMedia(MODE_IMAGE, img.src));
    if (showVideo) setViewerPrompt(promptForMedia(MODE_VIDEO, video.src));
    if (showImage) fitImageToStage();

    hideLoading();
}

function setVideoEngine(engine) {
    state.videoEngine = engine;
    const isAi = engine === "ai";
    document.getElementById("video-engine-manim").classList.toggle("active", !isAi);
    document.getElementById("video-engine-manim").setAttribute("aria-pressed", String(!isAi));
    document.getElementById("video-engine-ai").classList.toggle("active", isAi);
    document.getElementById("video-engine-ai").setAttribute("aria-pressed", String(isAi));
    updateAiVideoControls();
}

function setAiVideoMode(mode) {
    state.aiVideoMode = mode;
    const isText = mode === "text";
    document.getElementById("ai-video-text").classList.toggle("active", isText);
    document.getElementById("ai-video-text").setAttribute("aria-pressed", String(isText));
    document.getElementById("ai-video-image-mode").classList.toggle("active", !isText);
    document.getElementById("ai-video-image-mode").setAttribute("aria-pressed", String(!isText));
    updateAiVideoControls();
}

function updateAiVideoControls() {
    const showAiControls = state.mode === MODE_VIDEO && state.videoEngine === "ai";
    const showImageSource = showAiControls && state.aiVideoMode === "image";
    document.getElementById("ai-video-type").style.display = showAiControls ? "inline-flex" : "none";
    document.getElementById("ai-video-image-source").style.display = showImageSource ? "flex" : "none";

    const uploadMode = document.getElementById("ai-video-source-type").value === "upload";
    document.getElementById("ai-video-history-field").style.display = uploadMode ? "none" : "flex";
    document.getElementById("ai-video-upload-field").style.display = uploadMode ? "flex" : "none";
}

function populateAiVideoImageOptions() {
    const select = document.getElementById("ai-video-image");
    select.replaceChildren();
    const images = historyItems.filter(item => item.type === MODE_IMAGE);
    if (images.length === 0) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "No generated images yet";
        option.disabled = true;
        option.selected = true;
        select.appendChild(option);
        return;
    }

    for (const [index, item] of images.entries()) {
        const option = document.createElement("option");
        option.value = item.url;
        option.textContent = item.prompt || `Generated image ${index + 1}`;
        select.appendChild(option);
    }
}

function toggleHistoryDrawer() {
    if (document.body.classList.contains("history-open")) {
        closeHistoryDrawer(true);
        return;
    }

    document.body.classList.add("history-open");
    document.getElementById("history-toggle").setAttribute("aria-expanded", "true");
    document.getElementById("history-close").focus();
}

function closeHistoryDrawer(returnFocus = false) {
    document.body.classList.remove("history-open");
    document.getElementById("history-toggle").setAttribute("aria-expanded", "false");
    if (returnFocus) document.getElementById("history-toggle").focus();
}

function showError(message) {
    document.getElementById("error").textContent = message || "Something went wrong.";
}

function setViewerPrompt(prompt) {
    document.getElementById("viewer-prompt").textContent = `Prompt: ${prompt || "Prompt unavailable"}`;
}

function promptForMedia(type, source) {
    if (!source) return "";
    const url = new URL(source, window.location.href).pathname;
    return historyItems.find(item => item.type === type && item.url === url)?.prompt || "";
}

function startLoading(mode) {
    state.loading = true;
    document.getElementById("error").textContent = "";

    const loadingEl = document.getElementById("loading");
    const loadingText = document.getElementById("loading-text");
    loadingText.textContent = mode === MODE_IMAGE
        ? "Generating image with Stable Diffusion..."
        : mode === MODE_AI_VIDEO
            ? "Generating local AI video... This may take several minutes."
            : "Rendering animation video with Manim...";

    loadingEl.classList.remove("hidden");

    const bar = document.getElementById("progress-bar");
    const pctEl = document.getElementById("progress-text");
    const estSeconds = ESTIMATED_LOAD_SECONDS[mode] || 60;
    const startedAt = Date.now();

    stopProgress();
    progressTimer = setInterval(() => {
        const elapsed = (Date.now() - startedAt) / 1000;
        const pct = Math.min(95, Math.round((elapsed / estSeconds) * 100));
        bar.style.width = pct + "%";
        pctEl.textContent = pct + "%";
    }, 250);
}

function stopProgress() {
    if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
    }
}

function finishLoading() {
    stopProgress();
    const bar = document.getElementById("progress-bar");
    const pctEl = document.getElementById("progress-text");
    bar.style.width = "100%";
    pctEl.textContent = "100%";
    document.getElementById("loading").classList.add("hidden");
    state.loading = false;
}

function hideLoading() {
    document.getElementById("loading").classList.add("hidden");
}

function fitImageToStage() {
    const img = document.getElementById("generated-image");
    const stage = document.getElementById("media-stage");
    if (!img.naturalWidth || !stage.clientWidth || !stage.clientHeight) return;

    const fitScale = Math.min(
        stage.clientWidth / img.naturalWidth,
        stage.clientHeight / img.naturalHeight
    );
    fittedImageSize = {
        width: img.naturalWidth * fitScale,
        height: img.naturalHeight * fitScale
    };
    img.style.visibility = "visible";
    applyZoom();
}

function applyZoom() {
    if (!fittedImageSize) return;

    const stage = document.getElementById("media-stage");
    const canvas = document.getElementById("image-canvas");
    const img = document.getElementById("generated-image");
    stage.style.overflow = zoomLevel > 1 ? "auto" : "hidden";
    const width = Math.round(fittedImageSize.width * zoomLevel);
    const height = Math.round(fittedImageSize.height * zoomLevel);

    canvas.style.width = `${Math.max(stage.clientWidth, width)}px`;
    canvas.style.height = `${Math.max(stage.clientHeight, height)}px`;
    img.style.width = `${width}px`;
    img.style.height = `${height}px`;

    document.getElementById("zoom-level").textContent = `${Math.round(zoomLevel * 100)}%`;
    document.getElementById("zoom-out").disabled = zoomLevel <= MIN_ZOOM;
    document.getElementById("zoom-in").disabled = zoomLevel >= MAX_ZOOM;
}

function zoomIn() {
    zoomLevel = Math.min(MAX_ZOOM, Math.round((zoomLevel + ZOOM_STEP) * 100) / 100);
    applyZoom();
}

function zoomOut() {
    zoomLevel = Math.max(MIN_ZOOM, Math.round((zoomLevel - ZOOM_STEP) * 100) / 100);
    applyZoom();
}

function resetZoom() {
    zoomLevel = 1;
    applyZoom();
}

async function toggleFullscreen() {
    const viewer = document.getElementById("viewer-shell");
    try {
        if (document.fullscreenElement === viewer) {
            await document.exitFullscreen();
        } else {
            zoomLevel = 1;
            applyZoom();
            await viewer.requestFullscreen();
        }
    } catch (err) {
        showError("Full screen is unavailable in this browser.");
    }
}

function syncFullscreenButton() {
    const viewer = document.getElementById("viewer-shell");
    const isFullscreen = document.fullscreenElement === viewer;
    const imageVisible = document.getElementById("generated-image").style.display !== "none";
    const videoVisible = document.getElementById("animation").style.display !== "none";
    viewer.style.display = isFullscreen ? "flex" : imageVisible || videoVisible ? "block" : "none";
    const button = document.getElementById("fullscreen-toggle");
    button.textContent = isFullscreen ? "×" : "⛶";
    button.title = isFullscreen ? "Exit full screen" : "Full screen";
    button.setAttribute("aria-label", button.title);
    if (document.getElementById("generated-image").style.display !== "none") fitImageToStage();
}

function addToHistory(item) {
    historyItems.unshift(item);
    populateAiVideoImageOptions();
    setHistoryType(item.type);
}

function setHistoryType(type) {
    historyType = type;
    const showImages = type === MODE_IMAGE;
    document.getElementById("history-images").classList.toggle("active", showImages);
    document.getElementById("history-images").setAttribute("aria-pressed", String(showImages));
    document.getElementById("history-videos").classList.toggle("active", !showImages);
    document.getElementById("history-videos").setAttribute("aria-pressed", String(!showImages));
    renderHistory();
}

async function loadHistory() {
    try {
        const response = await fetch("/history");
        if (!response.ok) return;
        const data = await response.json();

        historyItems = [];
        for (const img of data.images || []) {
            historyItems.push({ id: `img-${img.url}`, type: "image", url: img.url, prompt: img.prompt || "" });
        }
        for (const vid of data.videos || []) {
            historyItems.push({ id: `vid-${vid.url}`, type: "video", url: vid.url, prompt: vid.prompt || "" });
        }
        populateAiVideoImageOptions();
        renderHistory();
    } catch (err) {
        // History is non-critical; fail silently.
    }
}

function renderHistory() {
    const list = document.getElementById("history-list");
    list.innerHTML = "";
    const visibleItems = historyItems.filter(item => item.type === historyType);

    if (visibleItems.length === 0) {
        const empty = document.createElement("p");
        empty.className = "history-empty";
        empty.textContent = historyType === MODE_IMAGE ? "No images yet." : "No videos yet.";
        list.appendChild(empty);
        return;
    }

    for (const item of visibleItems) {
        const entry = document.createElement("div");
        entry.className = "history-entry";

        const btn = document.createElement("button");
        btn.className = "history-item";
        btn.type = "button";
        btn.title = item.prompt || "Prompt unavailable for this generation";

        if (item.type === "image") {
            const img = document.createElement("img");
            img.className = "history-thumb";
            img.src = item.url;
            img.alt = item.prompt || "Generated image";
            btn.appendChild(img);
        } else {
            const video = document.createElement("video");
            video.className = "history-video";
            video.src = item.url;
            video.muted = true;
            video.playsInline = true;
            video.preload = "metadata";
            btn.appendChild(video);
        }

        const prompt = document.createElement("span");
        prompt.className = "history-prompt";
        prompt.textContent = item.prompt || "Prompt unavailable";
        prompt.title = item.prompt || "Prompt unavailable for this generation";
        btn.appendChild(prompt);

        btn.addEventListener("click", () => openHistoryItem(item));
        entry.appendChild(btn);

        const deleteBtn = document.createElement("button");
        deleteBtn.className = "history-delete";
        deleteBtn.type = "button";
        deleteBtn.textContent = "\u{1F5D1}";
        deleteBtn.title = `Delete generated ${item.type}`;
        deleteBtn.setAttribute("aria-label", `Delete generated ${item.type}`);
        deleteBtn.addEventListener("click", () => deleteHistoryItem(item, deleteBtn));
        entry.appendChild(deleteBtn);
        list.appendChild(entry);
    }
}

async function deleteHistoryItem(item, button) {
    const label = item.type === "image" ? "image" : "video";
    if (!window.confirm(`Delete this generated ${label}? This cannot be undone.`)) return;

    button.disabled = true;
    try {
        const response = await fetch("/history", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type: item.type, url: item.url })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `Failed to delete ${label}`);

        const image = document.getElementById("generated-image");
        const video = document.getElementById("animation");
        if (item.type === "image" && image.style.display !== "none" && image.src && new URL(image.src).pathname === item.url) {
            image.removeAttribute("src");
            image.style.display = "none";
            document.getElementById("viewer-shell").style.display = "none";
            document.getElementById("viewer-controls").style.display = "none";
            document.getElementById("media-stage").style.display = "none";
            fittedImageSize = null;
        }
        if (item.type === "video" && video.style.display !== "none" && video.src && new URL(video.src).pathname === item.url) {
            video.pause();
            video.removeAttribute("src");
            video.load();
            video.style.display = "none";
            document.getElementById("viewer-shell").style.display = "none";
            document.getElementById("viewer-controls").style.display = "none";
            document.getElementById("media-stage").style.display = "none";
        }

        historyItems = historyItems.filter(historyItem => historyItem.id !== item.id);
        populateAiVideoImageOptions();
        renderHistory();
    } catch (err) {
        showError(err.message || `Failed to delete ${label}`);
        button.disabled = false;
    }
}

function openHistoryItem(item) {
    closeHistoryDrawer(false);
    setViewerPrompt(item.prompt);
    if (item.type === "image") {
        const img = document.getElementById("generated-image");
        const video = document.getElementById("animation");
        document.getElementById("viewer-shell").style.display = "block";
        document.getElementById("viewer-controls").style.display = "flex";
        document.getElementById("media-stage").style.display = "block";
        document.getElementById("image-canvas").style.display = "grid";
        img.src = item.url;
        img.style.display = "block";
        img.style.visibility = "hidden";
        video.pause();
        video.style.display = "none";
        document.getElementById("zoom-controls").style.display = "flex";
        zoomLevel = 1;
        if (img.complete && img.naturalWidth) fitImageToStage();
    } else {
        const video = document.getElementById("animation");
        document.getElementById("viewer-shell").style.display = "block";
        document.getElementById("viewer-controls").style.display = "flex";
        document.getElementById("media-stage").style.display = "block";
        document.getElementById("image-canvas").style.display = "none";
        video.src = item.url;
        video.style.display = "block";
        document.getElementById("generated-image").style.display = "none";
        document.getElementById("zoom-controls").style.display = "none";
    }
}

async function generateImage(prompt) {
    startLoading(MODE_IMAGE);
    try {
        const steps = Number(document.getElementById("image-quality").value);
        const guidanceScale = Number(document.getElementById("guidance-scale").value);
        const response = await fetch("/generate-image", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                prompt,
                style: document.getElementById("style-preset").value,
                steps,
                guidance_scale: guidanceScale
            })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Failed to generate image");

        const img = document.getElementById("generated-image");
        setViewerPrompt(prompt);
        document.getElementById("viewer-shell").style.display = "block";
        document.getElementById("viewer-controls").style.display = "flex";
        document.getElementById("media-stage").style.display = "block";
        document.getElementById("image-canvas").style.display = "grid";
        img.src = data.image_url;
        img.style.display = "block";
        img.style.visibility = "hidden";
        document.getElementById("animation").style.display = "none";
        document.getElementById("zoom-controls").style.display = "flex";
        zoomLevel = 1;
        if (img.complete && img.naturalWidth) fitImageToStage();

        addToHistory({ id: `img-${Date.now()}`, type: "image", url: data.image_url, prompt });
    } catch (err) {
        showError(err.message || "Failed to generate image");
    } finally {
        finishLoading();
    }
}

async function generateAnimation(prompt) {
    startLoading(MODE_VIDEO);
    try {
        const response = await fetch("/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Failed to generate animation");

        displayGeneratedVideo(data.video_url, prompt);
    } catch (err) {
        showError(err.message || "Failed to generate animation");
    } finally {
        finishLoading();
    }
}

async function generateAiVideo(prompt) {
    startLoading(MODE_AI_VIDEO);
    try {
        const requestMode = state.aiVideoMode;
        let body;
        const headers = {};

        if (requestMode === "text") {
            headers["Content-Type"] = "application/json";
            body = JSON.stringify({ mode: "text", prompt });
        } else if (document.getElementById("ai-video-source-type").value === "history") {
            const imageUrl = document.getElementById("ai-video-image").value;
            if (!imageUrl) throw new Error("Choose a generated image or upload an image first.");
            headers["Content-Type"] = "application/json";
            body = JSON.stringify({ mode: "image", prompt, image_url: imageUrl });
        } else {
            const imageFile = document.getElementById("ai-video-upload").files[0];
            if (!imageFile) throw new Error("Choose an image to animate.");
            body = new FormData();
            body.append("mode", "image");
            body.append("prompt", prompt);
            body.append("image", imageFile);
        }

        const response = await fetch("/generate-ai-video", { method: "POST", headers, body });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Failed to generate AI video");
        displayGeneratedVideo(data.video_url, prompt);
    } catch (err) {
        showError(err.message || "Failed to generate AI video");
    } finally {
        finishLoading();
    }
}

function displayGeneratedVideo(videoUrl, prompt) {
    const video = document.getElementById("animation");
    setViewerPrompt(prompt);
    document.getElementById("viewer-shell").style.display = "block";
    document.getElementById("viewer-controls").style.display = "flex";
    document.getElementById("media-stage").style.display = "block";
    document.getElementById("image-canvas").style.display = "none";
    video.src = videoUrl;
    video.style.display = "block";
    document.getElementById("generated-image").style.display = "none";
    document.getElementById("zoom-controls").style.display = "none";
    addToHistory({ id: `vid-${Date.now()}`, type: "video", url: videoUrl, prompt });
}

async function generate() {
    if (state.loading) return;

    const prompt = document.getElementById("prompt").value.trim();
    if (!prompt) {
        showError("Please enter a prompt.");
        return;
    }

    const generateBtn = document.getElementById("generate-btn");
    generateBtn.disabled = true;

    try {
        if (state.mode === MODE_IMAGE) {
            await generateImage(prompt);
        } else if (state.videoEngine === "ai") {
            await generateAiVideo(prompt);
        } else {
            await generateAnimation(prompt);
        }
    } finally {
        generateBtn.disabled = false;
    }
}

function updateImageSettingsLabels() {
    document.getElementById("quality-value").textContent = `${document.getElementById("image-quality").value} steps`;
    document.getElementById("guidance-value").textContent = Number(document.getElementById("guidance-scale").value).toFixed(1);
}

document.getElementById("image-quality").addEventListener("input", updateImageSettingsLabels);
document.getElementById("guidance-scale").addEventListener("input", updateImageSettingsLabels);
document.getElementById("generated-image").addEventListener("load", fitImageToStage);
document.addEventListener("fullscreenchange", syncFullscreenButton);
document.addEventListener("keydown", event => {
    if (event.key === "Escape" && document.body.classList.contains("history-open")) {
        closeHistoryDrawer(true);
    }
});
window.addEventListener("resize", () => {
    fitImageToStage();
    if (window.innerWidth > 700) closeHistoryDrawer(false);
});
loadHistory();
