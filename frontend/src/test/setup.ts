import { configure } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// Les validations zod et les popovers Radix sont asynchrones : marge pour une machine chargée.
configure({ asyncUtilTimeout: 3000 });

// jsdom n'implémente ni ResizeObserver ni scrollIntoView, utilisés par cmdk et les Popover Radix
// (shared/ui/combobox.tsx).
if (!("ResizeObserver" in globalThis)) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
Element.prototype.scrollIntoView ??= () => {};
