import "@testing-library/jest-dom/vitest";

// jsdom lacks IntersectionObserver; some components or libs may touch it.
if (typeof window !== "undefined" && !window.IntersectionObserver) {
  class FakeIntersectionObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  // @ts-expect-error minimal polyfill for tests
  window.IntersectionObserver = FakeIntersectionObserver;
}
