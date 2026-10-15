// Applique la classe `dark` avant le premier paint pour éviter un flash du mauvais thème —
// doit rester synchronisé avec src/shared/theme/ThemeProvider.tsx (même clé, même repli sur
// le mode nuit par défaut). AuthLayout retire ensuite cette classe sur les pages publiques.
// Fichier séparé plutôt que script en ligne : la Content-Security-Policy de production
// (deploy/Caddyfile) n'autorise que les scripts servis par le site lui-même.
(function () {
  var stocke = null;
  try {
    stocke = localStorage.getItem("gfs-theme");
  } catch (_erreur) {
    // Stockage bloqué (navigation privée stricte) : mode nuit par défaut.
  }
  if (stocke !== "light") document.documentElement.classList.add("dark");
})();
