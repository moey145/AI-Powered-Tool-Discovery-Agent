import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

window.scrollTo = vi.fn();
// jsdom has no layout, so it doesn't implement scrolling an element into view.
Element.prototype.scrollIntoView = vi.fn();
