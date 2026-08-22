/* Image lightbox: intentionally small and dependency-free. */
document.addEventListener("DOMContentLoaded", () => {
  const dialog = document.querySelector(".lightbox");
  if (!dialog) return;
  const image = dialog.querySelector("img");
  const caption = dialog.querySelector("#lightbox-caption");

  document.querySelectorAll("[data-lightbox-src]").forEach((button) => {
    button.addEventListener("click", () => {
      image.src = button.dataset.lightboxSrc;
      image.alt = button.dataset.lightboxAlt || "";
      caption.textContent = button.dataset.lightboxCaption || "";
      dialog.showModal();
    });
  });

  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  dialog.addEventListener("close", () => {
    image.src = "";
    image.alt = "";
  });
});
