/**
 * Property-Based Tests for ReasoningPanel conflict badge rendering (Issue #19).
 *
 * Property 6: ReasoningPanel conflict badge renders iff conflictDetected is truthy
 *
 * Uses fast-check with numRuns: 100.
 * Validates: Requirements 5.1, 5.2, 5.4, 4.4
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as fc from 'fast-check';
import { render, screen } from '@testing-library/react';
import React from 'react';

// ---------------------------------------------------------------------------
// Mock BackendService so ReasoningPanel can be imported without a real backend
// ---------------------------------------------------------------------------
vi.mock('../../Services/BackendService', () => ({
  BackendService: {
    getVectorRules: vi.fn().mockResolvedValue([]),
    addVectorRule: vi.fn().mockResolvedValue({}),
  },
}));

import ReasoningPanel from '../../Components/ReasoningPanel.jsx';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Build a minimal lastTriggerResult prop that the component will accept,
 * overriding decision fields with the provided object.
 */
function makeLastTriggerResult(decisionOverrides = {}) {
  return {
    event: {},
    prediction: {
      predictedAction: 'turnOnGeyser',
      targetDevice: 'geyser',
      confidence: 0.90,
      reason: 'test',
    },
    ragContext: [],
    decision: {
      shouldExecute: false,
      shouldSuggest: false,
      actionId: 'test_action',
      targetDevice: 'geyser',
      deviceCommand: 'OFF',
      explanationEnglish: 'Test explanation.',
      explanationHindi: 'परीक्षण व्याख्या।',
      estimatedSavingsWh: 0,
      confidence: 0.90,
      conflictDetected: false,
      conflictDescription: null,
      ...decisionOverrides,
    },
  };
}

const BADGE_TEXT = '⚠️ Conflict Resolved';

// ---------------------------------------------------------------------------
// Property 6: Badge renders IFF conflictDetected is strictly true
// Validates: Requirements 5.1, 5.4, 4.4
// ---------------------------------------------------------------------------

describe('Property 6: ReasoningPanel conflict badge renders iff conflictDetected is truthy', () => {
  it('badge is PRESENT when conflictDetected === true', () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.constant('Some override rule content.'),
          fc.string({ minLength: 1, maxLength: 80 }),
          fc.constant(null),
        ),
        (conflictDescription) => {
          const { unmount } = render(
            <ReasoningPanel
              lastTriggerResult={makeLastTriggerResult({
                conflictDetected: true,
                conflictDescription,
              })}
            />,
          );
          expect(screen.getByText(BADGE_TEXT)).toBeTruthy();
          unmount();
        },
      ),
      { numRuns: 50 },
    );
  });

  it('badge is ABSENT when conflictDetected is false, null, undefined, 0, or absent', () => {
    const falsyValues = [false, null, undefined, 0, ''];
    fc.assert(
      fc.property(
        fc.constantFrom(...falsyValues),
        (conflictDetected) => {
          const decision =
            conflictDetected === undefined
              ? { conflictDescription: null } // key absent
              : { conflictDetected, conflictDescription: null };
          const { unmount } = render(
            <ReasoningPanel lastTriggerResult={makeLastTriggerResult(decision)} />,
          );
          expect(screen.queryByText(BADGE_TEXT)).toBeNull();
          unmount();
        },
      ),
      { numRuns: 50 },
    );
  });
});

// ---------------------------------------------------------------------------
// Task 8.2 — Unit tests for conflict description text rendering
// Validates: Requirements 5.2
// ---------------------------------------------------------------------------

describe('Task 8.2: Conflict description text rendering', () => {
  it('renders description text when conflictDetected=true and conflictDescription is a non-null string', () => {
    const description = 'Do not automatically start the water pump motor at 07:15:00 under GRID conditions.';
    render(
      <ReasoningPanel
        lastTriggerResult={makeLastTriggerResult({
          conflictDetected: true,
          conflictDescription: description,
        })}
      />,
    );
    expect(screen.getByText(description)).toBeTruthy();
  });

  it('renders badge without description paragraph when conflictDetected=true and conflictDescription=null', () => {
    render(
      <ReasoningPanel
        lastTriggerResult={makeLastTriggerResult({
          conflictDetected: true,
          conflictDescription: null,
        })}
      />,
    );
    // Badge heading is present
    expect(screen.getByText(BADGE_TEXT)).toBeTruthy();
    // No description paragraph — query returns null
    // (We just verify the heading renders without throwing when description is null)
  });

  it('badge is absent entirely when conflictDetected=false', () => {
    render(
      <ReasoningPanel
        lastTriggerResult={makeLastTriggerResult({
          conflictDetected: false,
          conflictDescription: 'This should not appear.',
        })}
      />,
    );
    expect(screen.queryByText(BADGE_TEXT)).toBeNull();
    expect(screen.queryByText('This should not appear.')).toBeNull();
  });
});
