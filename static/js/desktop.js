/* Desktop-only integration. Ordinary browser behavior is retained. */
(() => {
  let exporting = false;
  const isDesktop = () => Boolean(window.pywebview?.api?.save_report);

  function adaptLinks() {
    if (!isDesktop()) return;
    document.querySelectorAll('a[target="_blank"]').forEach(link => {
      if (new URL(link.href, location.href).origin === location.origin) link.target = "_self";
    });
  }
  window.addEventListener("pywebviewready", adaptLinks);
  adaptLinks();

  window.addEventListener("gradebook:before-close", event => {
    if (exporting) event.preventDefault();
  });

  document.addEventListener("submit", async event => {
    const button = event.submitter;
    if (!isDesktop() || button?.name !== "action" || button.value !== "export") return;
    event.preventDefault();
    if (exporting) return;
    const form = event.target;
    // Buttons named "action" shadow form.action with a RadioNodeList.
    const url = new URL(form.getAttribute("action") || location.href, location.href);
    if (url.origin !== location.origin) return;
    const data = new FormData(form);
    data.append(button.name, button.value);
    exporting = true;
    button.disabled = true;
    try {
      const response = await fetch(url, {method:"POST", body:data, credentials:"same-origin"});
      const disposition = response.headers.get("Content-Disposition") || "";
      if (!response.ok) throw new Error(`Export failed / ไม่สามารถส่งออกได้ (${response.status})`);
      if (!disposition.toLowerCase().startsWith("attachment")) {
        // Render the server's normal form errors/refreshed preview, including scripts.
        const html = await response.text();
        document.open(); document.write(html); document.close();
        return;
      }
      const utf8Name = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      const plainName = disposition.match(/filename="([^"]+)"|filename=([^;]+)/i);
      const name = utf8Name ? decodeURIComponent(utf8Name[1]) : (plainName?.[1] || plainName?.[2] || "report.docx").trim();
      const encoded = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(",")[1]);
        reader.onerror = () => reject(new Error("Could not read report / ไม่สามารถอ่านรายงานได้"));
        response.blob().then(blob => reader.readAsDataURL(blob), reject);
      });
      await window.pywebview.api.save_report(name, encoded);
    } catch (error) {
      window.alert(`${error.message || error}\nPlease try again / กรุณาลองอีกครั้ง`);
    } finally {
      exporting = false;
      button.disabled = false;
    }
  });
})();
