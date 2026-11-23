/* Perilaku antarmuka TB-CMS: sidebar (desktop tetap, tablet/ponsel offcanvas), modal login,
   field tanggal, tombol mata password, kirim otomatis filter. Tanpa pustaka. */
(function () {
  "use strict";

  var body = document.body;
  var sidebar = document.getElementById("tbSidebar");
  var toggle = document.getElementById("tbToggle");
  var menuBuka = document.getElementById("tbMenuBuka");
  var scrim = document.getElementById("tbScrim");
  var desktop = window.matchMedia("(min-width: 1024px)");

  /* ---- Sidebar ---- */
  function setOffcanvas(buka) {
    body.classList.toggle("tb-offcanvas-buka", buka);
    if (menuBuka) menuBuka.setAttribute("aria-expanded", String(buka));
    if (buka && sidebar) {
      var pertama = sidebar.querySelector("a, button, select, input");
      if (pertama) pertama.focus({ preventScroll: true });
    } else if (!buka && menuBuka && document.activeElement && sidebar.contains(document.activeElement)) {
      menuBuka.focus();
    }
  }

  function setDesktopTertutup(tutup) {
    body.classList.toggle("tb-sidebar-tertutup", tutup);
    toggle.classList.toggle("tb-toggle--tertutup", tutup);
    toggle.setAttribute("aria-label", tutup ? "Tampilkan sidebar" : "Sembunyikan sidebar");
    toggle.title = tutup ? "Tampilkan sidebar" : "Sembunyikan sidebar";
  }

  if (toggle) {
    toggle.addEventListener("click", function () {
      if (desktop.matches) setDesktopTertutup(!body.classList.contains("tb-sidebar-tertutup"));
      else setOffcanvas(false);
    });
  }
  if (menuBuka) menuBuka.addEventListener("click", function () { setOffcanvas(true); });
  if (scrim) scrim.addEventListener("click", function () { setOffcanvas(false); });

  // Ganti ukuran layar: buang keadaan yang tidak berlaku di ukuran baru
  desktop.addEventListener("change", function () {
    setOffcanvas(false);
    setDesktopTertutup(false);
  });

  /* ---- Modal login ---- */
  var modalAktif = null;
  var pemicu = null;

  function bukaModal(id, dari) {
    var m = document.getElementById(id);
    if (!m) return;
    modalAktif = m; pemicu = dari;
    m.hidden = false;
    var isian = m.querySelector("input");
    if (isian) isian.focus();
  }
  function tutupModal() {
    if (!modalAktif) return;
    modalAktif.hidden = true;
    modalAktif = null;
    if (pemicu) pemicu.focus();
  }

  document.addEventListener("click", function (e) {
    var buka = e.target.closest("[data-buka-modal]");
    if (buka) {
      if (!desktop.matches) setOffcanvas(false);
      bukaModal(buka.getAttribute("data-buka-modal"), buka);
      return;
    }
    if (e.target.closest("[data-tutup-modal]") || (modalAktif && e.target === modalAktif)) tutupModal();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (modalAktif) tutupModal();
      else if (body.classList.contains("tb-offcanvas-buka")) setOffcanvas(false);
      return;
    }
    // Fokus tidak keluar dari modal saat Tab
    if (e.key === "Tab" && modalAktif) {
      var fokus = modalAktif.querySelectorAll("button, input, a[href]");
      if (!fokus.length) return;
      var awal = fokus[0], akhir = fokus[fokus.length - 1];
      if (e.shiftKey && document.activeElement === awal) { e.preventDefault(); akhir.focus(); }
      else if (!e.shiftKey && document.activeElement === akhir) { e.preventDefault(); awal.focus(); }
    }
  });

  /* ---- Tombol mata: tampilkan/sembunyikan password ---- */
  document.querySelectorAll("[data-lihat-password]").forEach(function (tombol) {
    tombol.addEventListener("click", function () {
      var input = tombol.parentElement.querySelector("input");
      var lihat = input.type === "password";
      input.type = lihat ? "text" : "password";
      tombol.setAttribute("aria-pressed", String(lihat));
      tombol.setAttribute("aria-label", lihat ? "Sembunyikan password" : "Tampilkan password");
    });
  });

  /* ---- Field tanggal: seluruh kontrol membuka pemilih tanggal ---- */
  document.querySelectorAll('input[type="date"]').forEach(function (input) {
    input.addEventListener("click", function () {
      if (typeof input.showPicker === "function") {
        try { input.showPicker(); } catch (err) { /* peramban menolak: pemilih bawaan tetap bisa dibuka manual */ }
      }
    });
  });

  /* ---- Kirim otomatis saat pilihan berubah (filter, faskes, tanggal) ---- */
  document.querySelectorAll("[data-kirim-otomatis]").forEach(function (el) {
    el.addEventListener("change", function () {
      if (el.form && el.form.reportValidity()) el.form.submit();
    });
  });

  /* ---- Simulasi sinkronisasi: cegah klik ganda ---- */
  document.querySelectorAll("form[data-proses-sinkron]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var tombol = form.querySelector("button");
      tombol.disabled = true;
      tombol.querySelector("span").textContent = "Memproses...";
    });
  });
})();
