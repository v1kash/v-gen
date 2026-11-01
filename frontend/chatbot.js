const MODE_IMAGE = "image";
const MODE_VIDEO = "video";

const state = {
    mode: MODE_IMAGE,
    loading: false,
};

// Rough estimated generation times (seconds) used to animate a progress bar client-side.
// The backend runs to completion before responding, so this is an estimate, not live progress.
const ESTIMATED_LOAD_SECONDS = {
    [MODE_IMAGE]: 60, // SDXL, 30 steps ≈ 25s on GPU + load time
    [MODE_VIDEO]: 180, // Manim render can take a couple of minutes
};

let progressTimer = null;
let zoomLevel = 1;
let historyItems = [];

function setMode(mode) {
    state.mode = mode;
    document.getElementById("mode-image").classList.toggle("active", mode === MODE_IMAGE);
    document.getElementById("mode-video").classList.toggle("active", mode === MODE_VIDEO);

    const img = document.getElementById("generated-image");
    const video = document.getElementById("animation");
    const zoomControls = document.getElementById("zoom-controls");

    if (mode === MODE_IMAGE) {
        img.style.display = "block";
        video.style.display = "none";
        zoomControls.style.display = "block";
    } else {
        video.style.display = "block";
        img.style.display = "none";
        zoomControls.style.display = "none";
    }

    hideLoading();
}

function showError(message) {
    document.getElementById("error").textContent = message || "Something went wrong.";
}

function startLoading(mode) {
    state.loading = true;
    document.getElementById("error").textContent = "";

    const loadingEl = document.getElementById("loading");
    const loadingText = document.getElementById("loading-text");
    loadingText.textContent = mode === MODE_IMAGE
        ? "Generating image with Stable Diffusion..."
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

function applyZoom() {
    const img = document.getElementById("generated-image");
    if (img) img.style.transform = `scale(${zoomLevel})`;
}

function zoomIn() {
    zoomLevel = Math.min(5, Math.round((zoomLevel + 0.25) * 100) / 100);
    applyZoom();
}

function zoomOut() {
    zoomLevel = Math.max(0.25, Math.round((zoomLevel - 0.25) * 100) / 100);
    applyZoom();
}

function resetZoom() {
    zoomLevel = 1;
    applyZoom();
}

function addToHistory(item) {
    historyItems.unshift(item);
    renderHistory();
}

async function loadHistory() {
    try {
        const response = await fetch("/history");
        if (!response.ok) return;
        const data = await response.json();

        historyItems = [];
        for (const img of data.images || []) {
            historyItems.push({ id: `img-${img.url}`, type: "image", url: img.url });
        }
        for (const vid of data.videos || []) {
            historyItems.push({ id: `vid-${vid.url}`, type: "video", url: vid.url });
        }
        renderHistory();
    } catch (err) {
        // History is non-critical; fail silently.
    }
}

function renderHistory() {
    const list = document.getElementById("history-list");
    list.innerHTML = "";

    if (history.length === 0) {
        const empty = document.createElement("p");
        empty.className = "history-empty";
        empty.textContent = "No generations yet.";
        list.appendChild(empty);
        return;
    }

    for (const item of historyItems) {
        const btn = document.createElement("button");
        btn.className = "history-item";
        btn.type = "button";
        btn.title = item.type === "image" ? "Open generated image" : "Open generated video";

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

        btn.addEventListener("click", () => openHistoryItem(item));
        list.appendChild(btn);
    }
}

function openHistoryItem(item) {
    if (item.type === "image") {
        const img = document.getElementById("generated-image");
        img.src = item.url;
        img.style.display = "block";
        document.getElementById("animation").style.display = "none";
        document.getElementById("zoom-controls").style.display = "block";
        zoomLevel = 1;
        applyZoom();
    } else {
        const video = document.getElementById("animation");
        video.src = item.url;
        video.style.display = "block";
        document.getElementById("generated-image").style.display = "none";
        document.getElementById("zoom-controls").style.display = "none";
    }
}

async function generateImage(prompt) {
    startLoading(MODE_IMAGE);
    try {
        const response = await fetch("/generate-image", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Failed to generate image");

        const img = document.getElementById("generated-image");
        img.src = data.image_url;
        img.style.display = "block";
        document.getElementById("animation").style.display = "none";
        document.getElementById("zoom-controls").style.display = "block";
        zoomLevel = 1;
        applyZoom();

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

        const video = document.getElementById("animation");
        video.src = data.video_url;
        video.style.display = "block";
        document.getElementById("generated-image").style.display = "none";
        document.getElementById("zoom-controls").style.display = "none";

        addToHistory({ id: `vid-${Date.now()}`, type: "video", url: data.video_url, prompt });
    } catch (err) {
        showError(err.message || "Failed to generate animation");
    } finally {
        finishLoading();
    }
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
        } else {
            await generateAnimation(prompt);
        }
    } finally {
        generateBtn.disabled = false;
    }
}

loadHistory();
