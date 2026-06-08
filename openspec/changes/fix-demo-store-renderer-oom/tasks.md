# Tasks — fix-demo-store-renderer-oom

## 1. Memoize loadStore by raw-string identity
- [x] 1.1 Add module-level `_cachedRaw` and `_cachedStore` slots
- [x] 1.2 Return cached parse when localStorage string is unchanged
- [x] 1.3 Invalidate cache on saveStore() and clearDemoRuns()
- [x] 1.4 SSR-safe (no window → empty)
- [x] 1.5 Survive JSON.parse errors without throwing

## 2. LRU-cap the store at 10 runs
- [x] 2.1 Add MAX_DEMO_RUNS = 10 module constant
- [x] 2.2 enforceCap() sorts by updated_at desc and slices to cap
- [x] 2.3 saveStore() applies enforceCap before writing
- [x] 2.4 Quota-exceeded fallback drops oldest half and retries once

## 3. Remove dead event dispatches
- [x] 3.1 Drop `demo-runs-changed` CustomEvent from saveStore()
- [x] 3.2 Drop `demo-runs-changed` CustomEvent from clearDemoRuns()

## 4. In-app Reset Demo affordance
- [x] 4.1 Wire RotateCcw icon button next to DEMO MODE pill
- [x] 4.2 Confirm-then-clear-then-toast-then-reload flow
- [x] 4.3 Title + aria-label for accessibility

## 5. Test coverage
- [x] 5.1 Memoization-by-identity (parse called once for repeated reads)
- [x] 5.2 Corrupted JSON survival
- [x] 5.3 LRU cap on bulk insert
- [x] 5.4 Post-clear cache invalidation

## 6. Validate + ship
- [x] 6.1 `pnpm lint` clean (0 errors)
- [x] 6.2 `pnpm exec tsc --noEmit` clean
- [x] 6.3 `pnpm test` 19/19 passing
- [x] 6.4 `openspec validate fix-demo-store-renderer-oom --strict`
- [ ] 6.5 ACR build → revision 5 → smoke
- [ ] 6.6 Archive change after smoke green
