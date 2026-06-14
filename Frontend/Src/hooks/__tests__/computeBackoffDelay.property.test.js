/**
 * Property-Based Tests for computeBackoffDelay.js
 *
 * Feature: issue-5-websocket, Property 1: Backoff delays are exponential, bounded, and monotonically non-decreasing
 * All properties use fast-check with numRuns: 100.
 */

// Feature: issue-5-websocket, Property 1: Backoff delays are exponential, bounded, and monotonically non-decreasing

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { computeBackoffDelay } from "../computeBackoffDelay.js";

describe("Property 1: computeBackoffDelay — exponential, bounded, monotonically non-decreasing", () => {
  it("for retryCount in [1..5], delay equals 1000 * 2^(retryCount-1)", () => {
    // Validates: Requirements 4.5, 4.6
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 5 }),
        (retryCount) => {
          const delay = computeBackoffDelay(retryCount);
          expect(delay).toBe(1000 * Math.pow(2, retryCount - 1));
        }
      ),
      { numRuns: 100 }
    );
  });

  it("successive delays are strictly greater than the previous (monotonicity)", () => {
    // Validates: Requirements 4.5
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 4 }),
        (retryCount) => {
          const delayA = computeBackoffDelay(retryCount);
          const delayB = computeBackoffDelay(retryCount + 1);
          expect(typeof delayA).toBe("number");
          expect(typeof delayB).toBe("number");
          expect(delayB).toBeGreaterThan(delayA);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("no delay in [1..5] exceeds 16000 ms", () => {
    // Validates: Requirements 4.5
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 5 }),
        (retryCount) => {
          const delay = computeBackoffDelay(retryCount);
          expect(delay).toBeLessThanOrEqual(16000);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("for retryCount > 5, returns \"exhausted\"", () => {
    // Validates: Requirements 4.6
    fc.assert(
      fc.property(
        fc.integer({ min: 6, max: 1000 }),
        (retryCount) => {
          expect(computeBackoffDelay(retryCount)).toBe("exhausted");
        }
      ),
      { numRuns: 100 }
    );
  });

  it("boundary: retryCount 5 returns 16000 ms, retryCount 6 returns exhausted", () => {
    expect(computeBackoffDelay(5)).toBe(16000);
    expect(computeBackoffDelay(6)).toBe("exhausted");
  });
});
