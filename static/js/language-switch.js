(() => {
  "use strict";
  document.addEventListener("DOMContentLoaded", () => {
    const selector = document.querySelector(".language-switch");
    if (!selector) return;
    const toggle = selector.querySelector("#interface-language");
    const language = selector.querySelector('input[name="language"]');
    if (!toggle || !language) return;
    const initialChecked = toggle.checked;
    const status = document.getElementById("language-switch-status");
    const forms = [...document.querySelectorAll('main form[method="post"]')];
    const snapshot = form => JSON.stringify([...form.querySelectorAll("input,select,textarea")]
      .filter(input => input.name !== "csrfmiddlewaretoken")
      .map(input => [input.name || input.dataset.field || "", input.type,
        input.type === "file" ? [...input.files].map(file => [file.name, file.size, file.lastModified]) : input.value,
        input.checked]));
    const initial = new Map(forms.map(form => [form, snapshot(form)]));
    const updateSelection = () => {
      language.value = toggle.checked ? "th" : "en";
      selector.querySelectorAll("[data-language]").forEach(option => {
        option.classList.toggle("language-option-active", option.dataset.language === language.value);
      });
    };
    toggle.addEventListener("change", () => {
      updateSelection();
      status.hidden = true;
      selector.requestSubmit();
    });
    selector.addEventListener("submit", event => {
      const guard = new Event("gradebook:before-language-change", {cancelable:true});
      window.dispatchEvent(guard);
      if (guard.defaultPrevented || forms.some(form => snapshot(form) !== initial.get(form))) {
        event.preventDefault();
        toggle.checked = initialChecked;
        updateSelection();
        status.hidden = false;
        status.textContent = gettext("Save your changes before switching language. The current page will reload.");
      }
    });
  });
})();
