const dropzone = document.querySelector("[data-dropzone]");
const imageInput = document.getElementById("imageInput");
const checkpointInput = document.getElementById("checkpointInput");
const unsafeCheckpointToggle = document.getElementById("unsafeCheckpointToggle");
const unsafeCheckpointRow = document.getElementById("unsafeCheckpointRow");
const unsafeCheckpointHint = document.getElementById("unsafeCheckpointHint");
const deviceSelect = document.getElementById("deviceSelect");
const renderToggle = document.getElementById("renderToggle");
const uploadMeta = document.getElementById("uploadMeta");
const inputGallery = document.getElementById("inputGallery");
const form = document.getElementById("predictForm");
const progressList = document.getElementById("progressList");
const statusMessage = document.getElementById("statusMessage");
const statusSub = document.getElementById("statusSub");
const previewGrid = document.getElementById("previewGrid");
const resultList = document.getElementById("resultList");
const bundleLink = document.getElementById("bundleLink");
const warningBox = document.getElementById("warningBox");
const outputPath = document.getElementById("outputPath");
const setOutputFolderButton = document.getElementById("setOutputFolder");
const openOutputFolderButton = document.getElementById("openOutputFolder");
const toast = document.getElementById("toast");
const heroFrame = document.querySelector(".preview-frame");
const heroPlaceholder = document.querySelector(".preview-placeholder");
const submitButton = document.getElementById("submitButton");
const lightbox = document.getElementById("lightbox");
const lightboxMedia = document.getElementById("lightboxMedia");
const lightboxCaption = document.getElementById("lightboxCaption");

const progressTimers = [];
let previewIndex = 0;
let toastTimer = null;

const stageLabels = {
  prepare: "Preparing image",
  predict: "Predicting splats",
  render: "Rendering camera path",
  bundle: "Bundling outputs",
};

const stageStatus = {
  prepare: "Preparing image and extracting camera parameters.",
  predict: "Predicting Gaussian splats from the input.",
  render: "Rendering the camera path preview.",
  bundle: "Bundling outputs for download.",
};

function setStage(stage, state, label) {
  const item = progressList.querySelector(`[data-stage="${stage}"]`);
  if (!item) {
    return;
  }
  item.classList.remove("is-active", "is-done", "is-skipped");
  if (state === "active") {
    item.classList.add("is-active");
  } else if (state === "done") {
    item.classList.add("is-done");
  } else if (state === "skipped") {
    item.classList.add("is-skipped");
  }
  const badge = item.querySelector("em");
  if (badge) {
    badge.textContent = label || badge.textContent;
  }
}

function resetProgress(renderRequested) {
  ["prepare", "predict", "render", "bundle"].forEach((stage) => {
    setStage(stage, "", stage === "render" ? "Optional" : "Pending");
  });
  if (!renderRequested) {
    setStage("render", "skipped", "Skipped");
  }
}

function animateProgress(renderRequested) {
  clearProgressTimers();
  resetProgress(renderRequested);
  setStage("prepare", "active", stageLabels.prepare);
  progressTimers.push(
    setTimeout(() => {
      setStatus("Processing...", stageStatus.prepare);
    }, 300)
  );
  progressTimers.push(
    setTimeout(() => {
      setStage("prepare", "done", "Done");
      setStage("predict", "active", stageLabels.predict);
      setStatus("Processing...", stageStatus.predict);
    }, 700)
  );
  progressTimers.push(
    setTimeout(() => {
      setStage("predict", "done", "Done");
      if (renderRequested) {
        setStage("render", "active", stageLabels.render);
        setStatus("Processing...", stageStatus.render);
      }
    }, 1600)
  );
  progressTimers.push(
    setTimeout(() => {
      if (renderRequested) {
        setStage("render", "done", "Done");
      }
      setStage("bundle", "active", stageLabels.bundle);
      setStatus("Processing...", stageStatus.bundle);
    }, 2600)
  );
}

function finalizeProgress(renderEnabled) {
  clearProgressTimers();
  setStage("prepare", "done", "Done");
  setStage("predict", "done", "Done");
  if (renderEnabled) {
    setStage("render", "done", "Done");
  } else {
    setStage("render", "skipped", "Skipped");
  }
  setStage("bundle", "done", "Done");
}

function clearProgressTimers() {
  progressTimers.forEach((timer) => clearTimeout(timer));
  progressTimers.length = 0;
}

function updateUploadMeta(files) {
  if (!files || files.length === 0) {
    uploadMeta.textContent = "No files selected";
    return;
  }
  uploadMeta.textContent = `${files.length} file(s) selected`;
}

function setHeroMedia(src, type, alt) {
  heroFrame.querySelectorAll("img, video").forEach((node) => node.remove());
  if (!src) {
    heroPlaceholder.style.display = "block";
    return;
  }
  heroPlaceholder.style.display = "none";
  if (type === "video") {
    const video = document.createElement("video");
    video.src = src;
    video.muted = true;
    video.loop = true;
    video.playsInline = true;
    video.autoplay = true;
    heroFrame.appendChild(video);
  } else {
    const img = document.createElement("img");
    img.src = src;
    img.alt = alt || "Preview";
    if (src.startsWith("blob:")) {
      img.onload = () => URL.revokeObjectURL(src);
    }
    img.style.width = "100%";
    img.style.height = "100%";
    img.style.objectFit = "cover";
    heroFrame.appendChild(img);
  }
}

function updateHeroPreview(file) {
  if (!file) {
    setHeroMedia("", "image", "");
    return;
  }
  const objectUrl = URL.createObjectURL(file);
  setHeroMedia(objectUrl, "image", "Input preview");
}

function renderInputGallery(files) {
  inputGallery.innerHTML = "";
  if (!files || files.length === 0) {
    return;
  }
  Array.from(files).forEach((file, index) => {
    const chip = document.createElement("div");
    chip.className = "input-chip";
    chip.title = file.name;

    const img = document.createElement("img");
    img.src = URL.createObjectURL(file);
    img.alt = file.name;
    img.onload = () => URL.revokeObjectURL(img.src);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "x";
    removeBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      removeInputAt(index);
    });

    chip.appendChild(img);
    chip.appendChild(removeBtn);
    inputGallery.appendChild(chip);
  });
}

function removeInputAt(removeIndex) {
  const dt = new DataTransfer();
  Array.from(imageInput.files).forEach((file, index) => {
    if (index !== removeIndex) {
      dt.items.add(file);
    }
  });
  imageInput.files = dt.files;
  handleFiles(imageInput.files);
}

function handleFiles(files) {
  updateUploadMeta(files);
  renderInputGallery(files);
  updateHeroPreview(files && files.length ? files[0] : null);
}

function updateCheckpointUI() {
  if (!unsafeCheckpointRow || !unsafeCheckpointHint || !unsafeCheckpointToggle) {
    return;
  }
  const hasCheckpoint = checkpointInput.files && checkpointInput.files.length > 0;
  unsafeCheckpointRow.hidden = !hasCheckpoint;
  unsafeCheckpointHint.hidden = !hasCheckpoint;
  if (!hasCheckpoint) {
    unsafeCheckpointToggle.checked = false;
  }
}

function setStatus(message, sub) {
  statusMessage.textContent = message;
  statusSub.textContent = sub || "";
}

function showToast(message) {
  if (!toast) {
    return;
  }
  toast.textContent = message;
  toast.hidden = false;
  requestAnimationFrame(() => {
    toast.classList.add("is-visible");
  });
  if (toastTimer) {
    clearTimeout(toastTimer);
  }
  toastTimer = setTimeout(() => {
    toast.classList.remove("is-visible");
    setTimeout(() => {
      toast.hidden = true;
    }, 200);
  }, 3000);
}

async function refreshOutputRoot() {
  if (!outputPath) {
    return;
  }
  try {
    const response = await fetch("/api/output-root");
    if (!response.ok) {
      throw new Error("Unable to read output folder.");
    }
    const data = await response.json();
    outputPath.textContent = data.path || "Unknown";
  } catch (error) {
    outputPath.textContent = "Unavailable";
  }
}

async function chooseOutputFolder() {
  if (!setOutputFolderButton) {
    return;
  }
  setOutputFolderButton.disabled = true;
  try {
    const response = await fetch("/api/output-root/select", { method: "POST" });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Unable to set output folder.");
    }
    const data = await response.json();
    if (outputPath) {
      outputPath.textContent = data.path || "Unknown";
    }
    if (data.changed) {
      showToast("Output folder updated.");
    }
  } catch (error) {
    setStatus("Output folder unchanged.", error.message || "");
  } finally {
    setOutputFolderButton.disabled = false;
  }
}

async function openOutputFolder() {
  if (!openOutputFolderButton) {
    return;
  }
  openOutputFolderButton.disabled = true;
  try {
    const response = await fetch("/api/output-root/open", { method: "POST" });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Unable to open output folder.");
    }
  } catch (error) {
    setStatus("Unable to open output folder.", error.message || "");
  } finally {
    openOutputFolderButton.disabled = false;
  }
}

function resetResults() {
  previewGrid.innerHTML = "";
  resultList.innerHTML = "";
  bundleLink.hidden = true;
  warningBox.hidden = true;
  warningBox.textContent = "";
  previewIndex = 0;
}

function appendResultItem(label, url) {
  const item = document.createElement("div");
  item.className = "result-item";
  const name = document.createElement("span");
  name.textContent = label;
  const link = document.createElement("a");
  link.href = url;
  link.textContent = "Download";
  link.target = "_blank";
  item.appendChild(name);
  item.appendChild(link);
  resultList.appendChild(item);
}

function showSkeletons(count) {
  previewGrid.innerHTML = "";
  for (let i = 0; i < count; i += 1) {
    const tile = document.createElement("div");
    tile.className = "preview-tile is-skeleton";
    if (i === 0) {
      tile.classList.add("is-featured");
    }
    previewGrid.appendChild(tile);
  }
}

function addPreviewTile(url, isVideo, label, isFeatured) {
  const tile = document.createElement("div");
  tile.className = "preview-tile";
  if (isFeatured) {
    tile.classList.add("is-featured");
  }
  tile.style.animationDelay = `${Math.min(previewIndex * 0.08, 0.6)}s`;
  previewIndex += 1;
  tile.dataset.src = url;
  tile.dataset.type = isVideo ? "video" : "image";
  tile.dataset.label = label || "";

  if (isVideo) {
    const video = document.createElement("video");
    video.src = url;
    video.controls = false;
    video.muted = true;
    video.playsInline = true;
    video.loop = true;
    tile.appendChild(video);

    tile.addEventListener("mouseenter", () => {
      video.play().catch(() => {});
    });
    tile.addEventListener("mouseleave", () => {
      video.pause();
      video.currentTime = 0;
    });
  } else {
    const img = document.createElement("img");
    img.src = url;
    img.alt = "Output preview";
    tile.appendChild(img);
  }

  const overlay = document.createElement("div");
  overlay.className = "tile-overlay";
  overlay.textContent = label || (isVideo ? "Rendered pass" : "Input preview");
  tile.appendChild(overlay);

  tile.addEventListener("click", () => {
    openLightbox(tile.dataset.src, tile.dataset.type, tile.dataset.label);
  });

  previewGrid.appendChild(tile);
}

function setLoadingState(isLoading) {
  if (submitButton) {
    submitButton.disabled = isLoading;
    submitButton.classList.toggle("is-loading", isLoading);
    const label = submitButton.querySelector(".btn-label");
    if (label) {
      label.textContent = isLoading ? "Processing..." : "Create 3D Gaussian Scene";
    }
  }
  imageInput.disabled = isLoading;
  checkpointInput.disabled = isLoading;
  if (unsafeCheckpointToggle) {
    unsafeCheckpointToggle.disabled = isLoading;
  }
  deviceSelect.disabled = isLoading;
  renderToggle.disabled = isLoading;
}

function openLightbox(src, type, label) {
  if (!lightbox || !lightboxMedia) {
    return;
  }
  lightboxMedia.innerHTML = "";
  if (type === "video") {
    const video = document.createElement("video");
    video.src = src;
    video.controls = true;
    video.autoplay = true;
    video.playsInline = true;
    lightboxMedia.appendChild(video);
  } else {
    const img = document.createElement("img");
    img.src = src;
    img.alt = label || "Preview";
    lightboxMedia.appendChild(img);
  }
  if (lightboxCaption) {
    lightboxCaption.textContent = label || "";
  }
  lightbox.hidden = false;
  document.body.style.overflow = "hidden";
}

function closeLightbox() {
  if (!lightbox || !lightboxMedia) {
    return;
  }
  lightbox.hidden = true;
  lightboxMedia.innerHTML = "";
  if (lightboxCaption) {
    lightboxCaption.textContent = "";
  }
  document.body.style.overflow = "";
}

function scrollToStudio() {
  document.getElementById("studio").scrollIntoView({ behavior: "smooth" });
}

["primaryCta", "scrollToStudio", "secondaryCta"].forEach((id) => {
  const button = document.getElementById(id);
  if (button) {
    button.addEventListener("click", scrollToStudio);
  }
});

if (setOutputFolderButton) {
  setOutputFolderButton.addEventListener("click", chooseOutputFolder);
}

if (openOutputFolderButton) {
  openOutputFolderButton.addEventListener("click", openOutputFolder);
}

if (lightbox) {
  lightbox.addEventListener("click", (event) => {
    if (event.target.matches("[data-close]")) {
      closeLightbox();
    }
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeLightbox();
  }
});

if (dropzone) {
  dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropzone.classList.add("is-active");
  });
  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("is-active");
  });
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-active");
    const dt = new DataTransfer();
    Array.from(event.dataTransfer.files).forEach((file) => dt.items.add(file));
    imageInput.files = dt.files;
    handleFiles(imageInput.files);
  });
}

imageInput.addEventListener("change", () => handleFiles(imageInput.files));
checkpointInput.addEventListener("change", updateCheckpointUI);
updateCheckpointUI();
refreshOutputRoot();

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetResults();

  if (!imageInput.files || imageInput.files.length === 0) {
    setStatus("Please select at least one image.", "");
    return;
  }

  const renderRequested = renderToggle.checked;
  animateProgress(renderRequested);
  setStatus(
    "Processing...",
    `Uploading ${imageInput.files.length} image(s) for inference.`
  );
  showSkeletons(Math.min(4, imageInput.files.length));
  setLoadingState(true);

  const formData = new FormData();
  Array.from(imageInput.files).forEach((file) => formData.append("images", file));
  formData.append("device", deviceSelect.value);
  formData.append("render", renderRequested ? "true" : "false");
  if (unsafeCheckpointToggle && unsafeCheckpointToggle.checked) {
    formData.append("unsafe_checkpoint", "true");
  }
  if (checkpointInput.files && checkpointInput.files[0]) {
    formData.append("checkpoint", checkpointInput.files[0]);
  }

  try {
    const response = await fetch("/api/predict", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Request failed");
    }

    const data = await response.json();
    finalizeProgress(data.render_enabled);
    setStatus("Complete", `Device: ${data.device}. ${data.outputs.length} file(s) processed.`);

    previewGrid.innerHTML = "";
    previewIndex = 0;

    if (data.warnings && data.warnings.length) {
      warningBox.textContent = data.warnings.join(" ");
      warningBox.hidden = false;
    }

    bundleLink.href = data.bundle;
    bundleLink.hidden = false;
    bundleLink.textContent = "Download bundle";

    data.outputs.forEach((output, index) => {
      addPreviewTile(output.preview, false, output.name, index === 0);
      appendResultItem(`${output.name} (.ply)`, output.ply);
      if (output.video) {
        addPreviewTile(output.video, true, `${output.name} render`, false);
        appendResultItem(`${output.name} (video)`, output.video);
      }
      if (output.depth_video) {
        appendResultItem(`${output.name} (depth video)`, output.depth_video);
      }
      if (index === 0) {
        setHeroMedia(output.preview, "image", output.name);
      }
    });
  } catch (error) {
    clearProgressTimers();
    resetProgress(false);
    setStatus("Error", error.message || "Something went wrong");
    previewGrid.innerHTML = "";
    previewIndex = 0;
  } finally {
    setLoadingState(false);
  }
});
