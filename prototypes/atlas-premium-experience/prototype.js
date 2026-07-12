(() => {
  const surfaceButtons = [...document.querySelectorAll("[data-surface-target]")];
  const surfaces = [...document.querySelectorAll(".surface")];
  const desktopButtons = [...document.querySelectorAll("[data-desktop-target]")];
  const desktopViews = [...document.querySelectorAll("[data-desktop-view]")];
  const homeButtons = [...document.querySelectorAll("[data-home-target]")];
  const homeStates = [...document.querySelectorAll("[data-home-state]")];
  const overlay = document.querySelector("[data-command-overlay]");
  const commandInput = document.querySelector("#command-input");
  const toastRegion = document.querySelector("[data-toast-region]");
  let toastTimer = 0;

  function selectSurface(name) {
    surfaces.forEach((surface) => {
      const selected = surface.id === `surface-${name}`;
      surface.hidden = !selected;
      surface.classList.toggle("is-active", selected);
    });
    surfaceButtons.forEach((button) => {
      const selected = button.dataset.surfaceTarget === name;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function selectDesktopView(name) {
    desktopViews.forEach((view) => {
      const selected = view.dataset.desktopView === name;
      view.hidden = !selected;
      view.classList.toggle("is-active", selected);
    });
    desktopButtons.forEach((button) => {
      const selected = button.dataset.desktopTarget === name;
      button.classList.toggle("is-selected", selected);
      if (selected) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function selectHomeState(name) {
    selectDesktopView("home");
    homeStates.forEach((state) => {
      const selected = state.dataset.homeState === name;
      state.hidden = !selected;
      state.classList.toggle("is-active", selected);
    });
    homeButtons.forEach((button) => {
      const selected = button.dataset.homeTarget === name;
      const isReviewControl = button.closest(".state-review-control");
      if (isReviewControl) {
        button.classList.toggle("is-selected", selected);
        button.setAttribute("aria-pressed", String(selected));
      }
    });
  }

  function showToast(message) {
    if (!toastRegion || !message) return;
    window.clearTimeout(toastTimer);
    toastRegion.textContent = message;
    toastRegion.hidden = false;
    toastTimer = window.setTimeout(() => {
      toastRegion.hidden = true;
    }, 2800);
  }

  function openCommandPalette() {
    if (!overlay) return;
    overlay.hidden = false;
    document.body.classList.add("has-overlay");
    window.setTimeout(() => commandInput?.focus(), 0);
  }

  function closeCommandPalette() {
    if (!overlay) return;
    overlay.hidden = true;
    document.body.classList.remove("has-overlay");
  }

  surfaceButtons.forEach((button) => {
    button.addEventListener("click", () => selectSurface(button.dataset.surfaceTarget));
  });

  desktopButtons.forEach((button) => {
    button.addEventListener("click", () => selectDesktopView(button.dataset.desktopTarget));
  });

  homeButtons.forEach((button) => {
    button.addEventListener("click", () => selectHomeState(button.dataset.homeTarget));
  });

  document.querySelectorAll("[data-toast]").forEach((control) => {
    control.addEventListener("click", () => showToast(control.dataset.toast));
  });

  document.querySelectorAll("[data-prototype-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const view = form.closest("[data-desktop-view]")?.dataset.desktopView;
      if (view === "home") selectDesktopView("ask");
      else showToast("Prototype result refreshed from the existing example data.");
    });
  });

  document.querySelectorAll("[data-command-open]").forEach((button) => {
    button.addEventListener("click", openCommandPalette);
  });

  document.querySelectorAll("[data-command-target]").forEach((button) => {
    button.addEventListener("click", () => {
      selectSurface("desktop");
      selectDesktopView(button.dataset.commandTarget);
      closeCommandPalette();
    });
  });

  overlay?.addEventListener("click", (event) => {
    if (event.target === overlay) closeCommandPalette();
  });

  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openCommandPalette();
      return;
    }
    if (event.key === "Escape") {
      closeCommandPalette();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      const form = document.activeElement?.closest?.("form");
      if (form?.matches("[data-prototype-form]")) form.requestSubmit();
    }
  });

  const params = new URLSearchParams(window.location.search);
  if (params.get("embed") === "1") document.body.classList.add("is-embedded");
  if (params.get("surface") === "website") selectSurface("website");
  if (params.get("view")) selectDesktopView(params.get("view"));
  if (params.get("home")) selectHomeState(params.get("home"));
})();
