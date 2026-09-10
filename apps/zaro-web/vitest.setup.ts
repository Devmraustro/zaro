import "@testing-library/jest-dom/vitest";

// jsdom in this toolchain does not expose Storage (Node 22+ shadows the global
// with an experimental getter). Auth tests assert that credentials are never
// written to browser storage, so install an in-memory Storage implementation
// to prove nothing is persisted.
class MemoryStorage implements Storage {
  private readonly store = new Map<string, string>();

  get length(): number {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.has(String(key)) ? this.store.get(String(key))! : null;
  }

  key(index: number): string | null {
    return [...this.store.keys()][index] ?? null;
  }

  removeItem(key: string): void {
    this.store.delete(String(key));
  }

  setItem(key: string, value: string): void {
    this.store.set(String(key), String(value));
  }
}

function installStorage(): void {
  const install = (target: object) => {
    for (const name of ["localStorage", "sessionStorage"] as const) {
      try {
        Object.defineProperty(target, name, {
          value: new MemoryStorage(),
          configurable: true,
          writable: true,
        });
      } catch {
        try {
          (target as Record<string, unknown>)[name] = new MemoryStorage();
        } catch {
          // If the environment forbids defining storage, skip silently.
        }
      }
    }
  };
  if (typeof window !== "undefined") {
    install(window);
  }
  install(globalThis);
}

installStorage();

// jsdom lacks IntersectionObserver; some components or libs may touch it.
if (typeof window !== "undefined" && !window.IntersectionObserver) {
  class FakeIntersectionObserver {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  // @ts-expect-error minimal polyfill for tests
  window.IntersectionObserver = FakeIntersectionObserver;
}