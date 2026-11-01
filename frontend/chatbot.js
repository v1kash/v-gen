async function generateAnimation() {
    const prompt = document.getElementById("prompt").value.trim();
    const video = document.getElementById("animation");
    const errorEl = document.getElementById("error");

    video.src = "";
    if (errorEl) errorEl.textContent = "";

    if (!prompt) {
        if (errorEl) errorEl.textContent = "Please enter a prompt.";
        return;
    }

    try {
        const response = await fetch("/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Failed to generate animation");
        }

        video.src = data.video_url;
    } catch (err) {
        video.src = "";
        if (errorEl) errorEl.textContent = err.message || "Something went wrong while generating the animation.";
    }
}
