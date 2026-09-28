import { createContext, type ReactNode, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";

const STORAGE_KEY = "gfs-theme";

function lireThemeInitial(): Theme {
  const stocke = localStorage.getItem(STORAGE_KEY);
  if (stocke === "light" || stocke === "dark") return stocke;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

const ThemeContext = createContext<{ theme: Theme; toggleTheme: () => void } | null>(null);

/**
 * Pose/retire la classe `dark` sur <html> (voir @custom-variant dark dans index.css) et
 * persiste le choix en localStorage. index.html applique la même lecture de manière synchrone
 * avant le montage de React, pour éviter un flash du mauvais thème au chargement — les deux
 * doivent rester alignés sur STORAGE_KEY et la même logique de repli sur prefers-color-scheme.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(lireThemeInitial);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  function toggleTheme() {
    setTheme((actuel) => (actuel === "dark" ? "light" : "dark"));
  }

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme doit être utilisé à l'intérieur de ThemeProvider.");
  }
  return context;
}
