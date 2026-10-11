/* Optional interactions only. All product content and guide text are static HTML. */
document.documentElement.classList.add("js");

const menu = document.querySelector(".menu-toggle");
const nav = document.querySelector("#site-nav");
if (menu && nav) {
  menu.hidden = false;
  const close = () => {
    nav.classList.remove("is-open");
    menu.setAttribute("aria-expanded", "false");
  };
  menu.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    menu.setAttribute("aria-expanded", String(open));
  });
  nav.addEventListener("click", (event) => {
    if (event.target.closest("a")) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && nav.classList.contains("is-open")) {
      close();
      menu.focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".header-inner")) close();
  });
  matchMedia("(min-width: 561px)").addEventListener("change", close);
}

const demo = document.querySelector(".demo-shell");
if (demo) {
  const input = demo.querySelector("#demo-translation");
  input.readOnly = false;
  const counter = demo.querySelector("#demo-counter");
  const save = demo.querySelector("[data-save]");
  const approve = demo.querySelector("[data-approve]");
  const badge = demo.querySelector("[data-draft-status]");
  const status = demo.querySelector(".demo-status");
  const proposal = demo.querySelector("[data-proposal]");
  const reviewState = demo.querySelector("[data-review-state]");
  const emptyProposal = proposal.textContent;
  const names = {
    overview: "Overview",
    translations: "Translations",
    review: "Review",
  };
  const segmenter =
    typeof Intl.Segmenter === "function"
      ? new Intl.Segmenter("it", { granularity: "grapheme" })
      : null;
  const length = (value) =>
    segmenter
      ? Array.from(segmenter.segment(value)).length
      : Array.from(value).length;
  let saved = null;
  let state = null;

  function showView(view) {
    for (const button of demo.querySelectorAll("[data-view]")) {
      const selected = button.dataset.view === view;
      button.setAttribute("aria-pressed", String(selected));
      demo.querySelector(`#demo-${button.dataset.view}`).hidden = !selected;
    }
    demo.querySelector("[data-current-view]").textContent = names[view];
  }

  function refresh() {
    const count = length(input.value);
    const over = count > 24;
    const dirty = saved !== null && input.value !== saved;
    input.setAttribute("aria-invalid", String(over));
    counter.textContent = `${count} / 24 characters${over ? ` · ${count - 24} over limit` : ""}`;
    counter.parentElement.classList.toggle("over-limit", over);
    save.disabled = input.value === (saved ?? "Conferma");
    badge.hidden = state === null;
    badge.textContent = dirty
      ? "Unsaved changes"
      : state === "approved"
        ? "Approved"
        : "Draft";
    badge.classList.toggle("is-approved", state === "approved" && !dirty);
    approve.disabled =
      saved === null || length(saved) > 24 || state === "approved";
    proposal.textContent = saved ?? emptyProposal;
    reviewState.textContent =
      saved !== null && length(saved) > 24
        ? "Over limit — shorten and save the draft before approval."
        : state === "approved"
          ? "Approved · ready for a change set"
          : state === "draft"
            ? "Draft · awaiting review"
            : "";
  }

  demo.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view));
  });
  input.addEventListener("input", () => {
    refresh();
    status.textContent = "";
  });
  save.addEventListener("click", () => {
    if (save.disabled) return;
    saved = input.value;
    state = "draft";
    refresh();
    status.textContent =
      length(saved) > 24
        ? "Demo draft saved. Shorten the text before it can be approved."
        : "Demo draft saved. Open Review to compare and approve it.";
  });
  approve.addEventListener("click", () => {
    if (approve.disabled) return;
    state = "approved";
    refresh();
    status.textContent =
      "Approved in this demo. In VerboFlex, you would now prepare a Bitbucket change set. No repository was changed.";
  });
  demo.querySelector("[data-reset]").addEventListener("click", () => {
    saved = null;
    state = null;
    input.value = "Conferma";
    refresh();
    showView("translations");
    status.textContent =
      "Demo reset. Your changes were only held in this page.";
  });
  refresh();
}

// Highlight the guide section currently being read, without moving keyboard focus.
const toc = document.querySelector(".guide-toc");
if (toc && "IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries.find((entry) => entry.isIntersecting);
      if (!visible) return;
      for (const link of toc.querySelectorAll("a")) {
        if (link.hash === `#${visible.target.id}`)
          link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      }
    },
    { rootMargin: "-15% 0px -65% 0px" },
  );
  document
    .querySelectorAll(".guide-content section")
    .forEach((section) => observer.observe(section));
}
