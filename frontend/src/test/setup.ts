import "@testing-library/jest-dom/vitest";

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
