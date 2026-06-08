/* Vitest setup. Provide an in-memory localStorage shim if the test env
 * doesn't supply a fully functional one. We do this even when jsdom is on
 * because jsdom 29 + vitest 4 sometimes ships a localStorage with read-only
 * semantics that lacks .clear().
 */
import { beforeEach } from "vitest";

class MemoryStorage {
  private store = new Map<string, string>();
  get length() { return this.store.size; }
  clear() { this.store.clear(); }
  getItem(k: string): string | null { return this.store.get(k) ?? null; }
  key(i: number): string | null { return Array.from(this.store.keys())[i] ?? null; }
  removeItem(k: string) { this.store.delete(k); }
  setItem(k: string, v: string) { this.store.set(k, String(v)); }
}

const memShim = new MemoryStorage();

// Force-replace any existing localStorage with our shim so .clear() etc.
// are guaranteed to exist.
Object.defineProperty(globalThis, "localStorage", {
  value: memShim,
  writable: true,
  configurable: true,
});

// Also stub the same shim onto window if jsdom is present, since the
// production code paths read window.localStorage explicitly.
if (typeof globalThis.window !== "undefined") {
  Object.defineProperty(globalThis.window, "localStorage", {
    value: memShim,
    writable: true,
    configurable: true,
  });
}

beforeEach(() => {
  memShim.clear();
});
