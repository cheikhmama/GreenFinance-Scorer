import { useEffect, useState } from "react";

/** Retarde la répercussion d'une valeur qui change vite (ex. saisie clavier) — évite une requête
 * réseau à chaque frappe pour un champ de recherche branché sur l'API. */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timeoutId);
  }, [value, delayMs]);

  return debounced;
}
