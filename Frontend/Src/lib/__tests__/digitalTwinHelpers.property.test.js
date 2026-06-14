/**
 * Property-Based Tests for digitalTwinHelpers.js
 *
 * All properties use fast-check with numRuns: 100.
 * Tag format: // Feature: live-2d-digital-twin, Property N: <property text>
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import {
  getNodeStyle,
  deriveRoomGlows,
  deriveCookerState,
  derivePresence,
  computeTotalLoad,
  computeNextStatus,
  deriveAmbientTheme,
  SENSOR_TO_ROOM,
} from '../digitalTwinHelpers.js';

// ---------------------------------------------------------------------------
// Shared arbitraries
// ---------------------------------------------------------------------------

const knownStatuses = [
  'OFF', 'STANDBY', 'ON', 'NORMAL',
  'MEDITATION_DIMS', 'STUDY_FOCUS_BRIGHTNESS',
  'DO_NOT_DISTURB', 'FAST_CHARGE', 'NORMAL_CHARGE',
];

const statusArb = fc.oneof(
  fc.constantFrom(...knownStatuses),
  fc.string(), // arbitrary unknown strings
);

const hexColorArb = fc.hexaString({ minLength: 6, maxLength: 6 }).map((h) => `#${h}`);

const roomKeys = Object.keys(SENSOR_TO_ROOM); // living, bedroom, bathroom, kitchen, pooja

// ---------------------------------------------------------------------------
// Property 1: Device node style is determined entirely by status
// ---------------------------------------------------------------------------
// Feature: live-2d-digital-twin, Property 1: Device node style is determined entirely by status

describe('Property 1: getNodeStyle', () => {
  const DIMMED_FILL = 'rgba(255,255,255,0.02)';
  const offStandby = new Set(['OFF', 'STANDBY']);

  it('OFF and STANDBY always return the dimmed fill', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('OFF', 'STANDBY'),
        hexColorArb,
        (status, roomColor) => {
          const style = getNodeStyle(status, roomColor);
          expect(style.fill).toBe(DIMMED_FILL);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('known active statuses return non-dimmed fills', () => {
    const activeStatuses = knownStatuses.filter((s) => !offStandby.has(s));
    fc.assert(
      fc.property(
        fc.constantFrom(...activeStatuses),
        hexColorArb,
        (status, roomColor) => {
          const style = getNodeStyle(status, roomColor);
          expect(style.fill).not.toBe(DIMMED_FILL);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('never throws for any string input', () => {
    fc.assert(
      fc.property(statusArb, hexColorArb, (status, roomColor) => {
        expect(() => getNodeStyle(status, roomColor)).not.toThrow();
        const style = getNodeStyle(status, roomColor);
        expect(style).toHaveProperty('fill');
        expect(style).toHaveProperty('stroke');
      }),
      { numRuns: 100 },
    );
  });

  it('unknown status strings get the dimmed appearance (fallback)', () => {
    // Generate strings that are guaranteed not to be a known status
    const unknownStatusArb = fc.string().filter((s) => !knownStatuses.includes(s));
    fc.assert(
      fc.property(unknownStatusArb, hexColorArb, (status, roomColor) => {
        const style = getNodeStyle(status, roomColor);
        expect(style.fill).toBe(DIMMED_FILL);
      }),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 2: Room glow opacity is correct for any device state combination
// ---------------------------------------------------------------------------
// Feature: live-2d-digital-twin, Property 2: Room glow opacity is correct for any device state combination

describe('Property 2: deriveRoomGlows', () => {
  // Non-kitchen rooms and the device keys the helper inspects
  const ROOM_DEVICE_KEYS = {
    living: ['television', 'livingRoomLights', 'speakerSystem'],
    bedroom: ['airConditioner'],
    bathroom: ['geyser'],
    pooja: ['poojaLights'],
    utility: ['waterMotor', 'inverterBackup'],
  };

  const deviceStatusArb = fc.record({
    status: statusArb,
    wattage: fc.nat(3000),
  });

  it('all-OFF/STANDBY non-kitchen rooms produce glow 0', () => {
    const offStatusArb = fc.constantFrom('OFF', 'STANDBY');
    fc.assert(
      fc.property(
        fc.record({
          television:      fc.record({ status: offStatusArb, wattage: fc.nat(3000) }),
          livingRoomLights:fc.record({ status: offStatusArb, wattage: fc.nat(3000) }),
          speakerSystem:   fc.record({ status: offStatusArb, wattage: fc.nat(3000) }),
          airConditioner:  fc.record({ status: offStatusArb, wattage: fc.nat(3000) }),
          geyser:          fc.record({ status: offStatusArb, wattage: fc.nat(3000) }),
          poojaLights:     fc.record({ status: offStatusArb, wattage: fc.nat(3000) }),
          waterMotor:      fc.record({ status: offStatusArb, wattage: fc.nat(3000) }),
          inverterBackup:  fc.record({ status: offStatusArb, wattage: fc.nat(3000) }),
        }),
        (devices) => {
          const glows = deriveRoomGlows(devices, {
            whistleCount: 0,
            targetWhistles: 0,
            isFastingDay: false,
          });
          const nonKitchenRooms = Object.keys(ROOM_DEVICE_KEYS);
          for (const room of nonKitchenRooms) {
            expect(glows[room]).toBe(0);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('at least one active device in a non-kitchen room produces glow > 0', () => {
    const activeStatusArb = fc.constantFrom(
      'ON', 'NORMAL', 'MEDITATION_DIMS', 'STUDY_FOCUS_BRIGHTNESS',
      'DO_NOT_DISTURB', 'FAST_CHARGE', 'NORMAL_CHARGE',
    );
    // Test each non-kitchen room individually
    const nonKitchenRoomEntries = Object.entries(ROOM_DEVICE_KEYS);
    fc.assert(
      fc.property(
        fc.constantFrom(...nonKitchenRoomEntries),
        activeStatusArb,
        deviceStatusArb,
        ([roomKey, deviceKeys], activeStatus, fallbackDevice) => {
          // Build a device map where at least one device in this room is active
          const devices = {};
          // All devices default to OFF first
          for (const keys of Object.values(ROOM_DEVICE_KEYS)) {
            for (const k of keys) {
              devices[k] = { status: 'OFF', wattage: 100 };
            }
          }
          // Set first device in this room to an active status
          devices[deviceKeys[0]] = { status: activeStatus, wattage: 100 };

          const glows = deriveRoomGlows(devices, {
            whistleCount: 0,
            targetWhistles: 0,
            isFastingDay: false,
          });
          expect(glows[roomKey]).toBeGreaterThan(0);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('kitchen glow is always 0 when isFastingDay is true, regardless of whistleCount', () => {
    fc.assert(
      fc.property(
        fc.nat(20),          // whistleCount
        fc.nat(20),          // targetWhistles
        (whistleCount, targetWhistles) => {
          const glows = deriveRoomGlows(
            {},
            { whistleCount, targetWhistles, isFastingDay: true },
          );
          expect(glows['kitchen']).toBe(0);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('kitchen glow > 0 when not fasting and targetWhistles > 0 and whistleCount > 0', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 20 }), // targetWhistles > 0
        fc.integer({ min: 1, max: 20 }), // whistleCount > 0
        (targetWhistles, whistleCount) => {
          const glows = deriveRoomGlows(
            {},
            { whistleCount, targetWhistles, isFastingDay: false },
          );
          expect(glows['kitchen']).toBeGreaterThan(0);
        },
      ),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 3: Cooker state derivation is division-safe and monotonically consistent
// ---------------------------------------------------------------------------
// Feature: live-2d-digital-twin, Property 3: Cooker state derivation is division-safe and monotonically consistent

describe('Property 3: deriveCookerState', () => {
  it('targetWhistles <= 0 always returns dormant', () => {
    fc.assert(
      fc.property(
        fc.nat(20),                          // whistleCount (non-negative)
        fc.integer({ min: -100, max: 0 }),   // targetWhistles <= 0
        (whistleCount, targetWhistles) => {
          const result = deriveCookerState({ whistleCount, targetWhistles });
          expect(result.state).toBe('dormant');
        },
      ),
      { numRuns: 100 },
    );
  });

  it('whistleCount >= targetWhistles > 0 returns done', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 20 }),  // targetWhistles > 0
        fc.nat(20),                        // extra (adds to reach count >= target)
        (targetWhistles, extra) => {
          const whistleCount = targetWhistles + extra;
          const result = deriveCookerState({ whistleCount, targetWhistles });
          expect(result.state).toBe('done');
        },
      ),
      { numRuns: 100 },
    );
  });

  it('0 <= whistleCount < targetWhistles returns active with progress in [0, 1)', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 20 }),  // targetWhistles > 0
        fc.nat(19),                        // will be clamped to < targetWhistles
        (targetWhistles, rawCount) => {
          const whistleCount = rawCount % targetWhistles; // guaranteed < targetWhistles
          const result = deriveCookerState({ whistleCount, targetWhistles });
          expect(result.state).toBe('active');
          expect(result.progress).toBeGreaterThanOrEqual(0);
          expect(result.progress).toBeLessThan(1);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('progress is non-decreasing as whistleCount increases (monotone property)', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 20 }),   // targetWhistles > 0
        fc.nat(18),                         // whistleCount_a
        fc.nat(1),                          // delta (added to a to get b)
        (targetWhistles, countA, delta) => {
          const countB = countA + delta + 1; // countB > countA
          const resultA = deriveCookerState({ whistleCount: countA, targetWhistles });
          const resultB = deriveCookerState({ whistleCount: countB, targetWhistles });
          expect(resultB.progress).toBeGreaterThanOrEqual(resultA.progress);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('never throws for any non-negative integer pair', () => {
    fc.assert(
      fc.property(
        fc.nat(100),
        fc.nat(100),
        (whistleCount, targetWhistles) => {
          expect(() => deriveCookerState({ whistleCount, targetWhistles })).not.toThrow();
        },
      ),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 4: Presence map correctly reflects motion events
// ---------------------------------------------------------------------------
// Feature: live-2d-digital-twin, Property 4: Presence map correctly reflects motion events

describe('Property 4: derivePresence', () => {
  const motionSensorIds = Object.keys(SENSOR_TO_ROOM); // e.g. "motion_living"
  const nonMotionStringArb = fc.string().filter(
    (s) => !s.startsWith('motion_'),
  );

  const eventArb = (sensorId) =>
    fc.record({ sensorId: fc.constant(sensorId), type: fc.string() });

  it('room appears in set iff eventHistory contains a matching motion_{roomKey} event', () => {
    fc.assert(
      fc.property(
        fc.subarray(motionSensorIds, { minLength: 0, maxLength: motionSensorIds.length }),
        (presentSensors) => {
          const events = presentSensors.map((sid) => ({ sensorId: sid }));
          const presence = derivePresence(events);
          // Every sensor we included → its room must be present
          for (const sid of presentSensors) {
            expect(presence.has(SENSOR_TO_ROOM[sid])).toBe(true);
          }
          // Every sensor we excluded → its room must NOT be present
          const absentSensors = motionSensorIds.filter((s) => !presentSensors.includes(s));
          for (const sid of absentSensors) {
            expect(presence.has(SENSOR_TO_ROOM[sid])).toBe(false);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('rooms do not appear from non-motion events', () => {
    fc.assert(
      fc.property(
        fc.array(nonMotionStringArb, { minLength: 0, maxLength: 10 }),
        (sensorIds) => {
          const events = sensorIds.map((sid) => ({ sensorId: sid }));
          const presence = derivePresence(events);
          // None of the known rooms should appear
          for (const roomKey of Object.values(SENSOR_TO_ROOM)) {
            expect(presence.has(roomKey)).toBe(false);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('returns empty Set for null input', () => {
    const presence = derivePresence(null);
    expect(presence.size).toBe(0);
  });

  it('returns empty Set for undefined input', () => {
    const presence = derivePresence(undefined);
    expect(presence.size).toBe(0);
  });

  it('returns empty Set for empty array', () => {
    fc.assert(
      fc.property(fc.constant([]), (arr) => {
        const presence = derivePresence(arr);
        expect(presence.size).toBe(0);
      }),
      { numRuns: 10 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 5: Total load calculation applies overrides and excludes zero-watt active devices
// Property 6: Load counter color threshold is applied consistently
// ---------------------------------------------------------------------------
// Feature: live-2d-digital-twin, Property 5: Total load calculation applies overrides
// Feature: live-2d-digital-twin, Property 6: Load counter color threshold

// Derive load counter color the same way the UI will
function loadColor(watts) {
  return watts > 1000 ? '#ffc837' : '#26c281';
}

describe('Property 5 & 6: computeTotalLoad', () => {
  const activeOverrideStatuses = ['MEDITATION_DIMS', 'STUDY_FOCUS_BRIGHTNESS', 'DO_NOT_DISTURB'];
  const overrideWatts = {
    MEDITATION_DIMS: 15,
    STUDY_FOCUS_BRIGHTNESS: 45,
    DO_NOT_DISTURB: 5,
  };

  it('OFF/STANDBY devices contribute 0 to total load', () => {
    const offStatusArb = fc.constantFrom('OFF', 'STANDBY');
    fc.assert(
      fc.property(
        fc.dictionary(
          fc.string({ minLength: 1, maxLength: 20 }),
          fc.record({ status: offStatusArb, wattage: fc.nat(3000) }),
        ),
        (devices) => {
          const load = computeTotalLoad(devices);
          expect(load).toBe(0);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('MEDITATION_DIMS contributes exactly 15W per device', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 10 }), // number of such devices
        (n) => {
          const devices = {};
          for (let i = 0; i < n; i++) {
            devices[`device_${i}`] = { status: 'MEDITATION_DIMS', wattage: 9999 };
          }
          expect(computeTotalLoad(devices)).toBe(15 * n);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('STUDY_FOCUS_BRIGHTNESS contributes exactly 45W per device', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 10 }),
        (n) => {
          const devices = {};
          for (let i = 0; i < n; i++) {
            devices[`device_${i}`] = { status: 'STUDY_FOCUS_BRIGHTNESS', wattage: 9999 };
          }
          expect(computeTotalLoad(devices)).toBe(45 * n);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('DO_NOT_DISTURB contributes exactly 5W per device', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 10 }),
        (n) => {
          const devices = {};
          for (let i = 0; i < n; i++) {
            devices[`device_${i}`] = { status: 'DO_NOT_DISTURB', wattage: 9999 };
          }
          expect(computeTotalLoad(devices)).toBe(5 * n);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('total load is always >= 0', () => {
    const arbitraryDevices = fc.dictionary(
      fc.string({ minLength: 1, maxLength: 20 }),
      fc.record({ status: statusArb, wattage: fc.nat(3000) }),
    );
    fc.assert(
      fc.property(arbitraryDevices, (devices) => {
        expect(computeTotalLoad(devices)).toBeGreaterThanOrEqual(0);
      }),
      { numRuns: 100 },
    );
  });

  it('Property 6: load > 1000 → color is amber #ffc837', () => {
    // Build a devices map that is guaranteed to exceed 1000W using ON status
    fc.assert(
      fc.property(
        fc.integer({ min: 2, max: 10 }),     // number of devices
        fc.integer({ min: 501, max: 3000 }), // each wattage > 500, so total > 1000
        (n, wattage) => {
          const devices = {};
          for (let i = 0; i < n; i++) {
            devices[`device_${i}`] = { status: 'ON', wattage };
          }
          const load = computeTotalLoad(devices);
          if (load > 1000) {
            expect(loadColor(load)).toBe('#ffc837');
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('Property 6: load <= 1000 → color is green #26c281', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 5 }),
        fc.integer({ min: 1, max: 200 }),    // small wattages so total <= 1000
        (n, wattage) => {
          const devices = {};
          for (let i = 0; i < n; i++) {
            devices[`device_${i}`] = { status: 'ON', wattage };
          }
          const load = computeTotalLoad(devices);
          if (load <= 1000) {
            expect(loadColor(load)).toBe('#26c281');
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('Property 6: color boundary — exactly 1000W is green, 1001W is amber', () => {
    expect(loadColor(1000)).toBe('#26c281');
    expect(loadColor(1001)).toBe('#ffc837');
  });
});

// ---------------------------------------------------------------------------
// Property 7: Toggle nextStatus is the inverse of current status
// ---------------------------------------------------------------------------
// Feature: live-2d-digital-twin, Property 7: Toggle nextStatus is the inverse of current status

describe('Property 7: computeNextStatus', () => {
  const nonKitchenRoomArb = fc.string().filter((r) => r !== 'kitchen');

  it('non-kitchen room: OFF → ON', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 20 }), // deviceKey
        nonKitchenRoomArb,
        (deviceKey, roomKey) => {
          expect(computeNextStatus(deviceKey, 'OFF', roomKey)).toBe('ON');
        },
      ),
      { numRuns: 100 },
    );
  });

  it('non-kitchen room: any status that is not OFF → OFF', () => {
    const nonOffStatusArb = statusArb.filter((s) => s !== 'OFF');
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 20 }), // deviceKey
        nonOffStatusArb,
        nonKitchenRoomArb,
        (deviceKey, status, roomKey) => {
          expect(computeNextStatus(deviceKey, status, roomKey)).toBe('OFF');
        },
      ),
      { numRuns: 100 },
    );
  });

  it('kitchen roomKey always returns null regardless of status', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 20 }), // deviceKey
        statusArb,
        (deviceKey, status) => {
          expect(computeNextStatus(deviceKey, status, 'kitchen')).toBeNull();
        },
      ),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 8: Ambient theme derivation respects priority hierarchy
// ---------------------------------------------------------------------------
// Feature: live-2d-digital-twin, Property 8: Ambient theme derivation respects priority hierarchy

describe('Property 8: deriveAmbientTheme', () => {
  const INVERTER_TINT_MARKER = '255,200,55';

  it('INVERTER powerStatus always produces bgTint containing the amber marker', () => {
    const timeStrArb = fc.oneof(
      fc.constant(''),
      fc.constant('not-a-time'),
      fc.constant('25:99:99'),
      fc.stringOf(fc.char(), { minLength: 0, maxLength: 20 }),
      // Valid time strings across all periods
      fc.integer({ min: 0, max: 23 }).map((h) => `${String(h).padStart(2, '0')}:00:00`),
    );

    fc.assert(
      fc.property(timeStrArb, (simulatedTime) => {
        const theme = deriveAmbientTheme({
          powerStatus: 'INVERTER',
          simulatedTime,
        });
        expect(theme.bgTint).toContain(INVERTER_TINT_MARKER);
      }),
      { numRuns: 100 },
    );
  });

  it('GRID powerStatus never produces the amber INVERTER marker in bgTint', () => {
    const timeStrArb = fc.integer({ min: 0, max: 23 }).map(
      (h) => `${String(h).padStart(2, '0')}:00:00`,
    );
    fc.assert(
      fc.property(timeStrArb, (simulatedTime) => {
        const theme = deriveAmbientTheme({ powerStatus: 'GRID', simulatedTime });
        // bgTint may be null (afternoon) or a non-amber value
        if (theme.bgTint !== null) {
          expect(theme.bgTint).not.toContain(INVERTER_TINT_MARKER);
        }
      }),
      { numRuns: 100 },
    );
  });

  it('INVERTER priority overrides all time-based values', () => {
    // Test every valid hour with INVERTER
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 23 }),
        (hour) => {
          const simulatedTime = `${String(hour).padStart(2, '0')}:00:00`;
          const theme = deriveAmbientTheme({ powerStatus: 'INVERTER', simulatedTime });
          expect(theme.bgTint).toContain(INVERTER_TINT_MARKER);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('malformed simulatedTime strings never throw', () => {
    const malformedArb = fc.oneof(
      fc.constant(''),
      fc.constant('not-a-time'),
      fc.constant('99:99:99'),
      fc.constant('abc:def'),
      fc.constant(null),
      fc.string(),
    );
    fc.assert(
      fc.property(malformedArb, (simulatedTime) => {
        expect(() =>
          deriveAmbientTheme({ powerStatus: 'GRID', simulatedTime }),
        ).not.toThrow();
      }),
      { numRuns: 100 },
    );
  });

  it('function never throws for any arbitrary systemState', () => {
    fc.assert(
      fc.property(
        fc.record({
          powerStatus: fc.oneof(fc.constant('INVERTER'), fc.constant('GRID'), fc.string()),
          simulatedTime: fc.oneof(fc.string(), fc.constant(null), fc.constant(undefined)),
        }),
        (systemState) => {
          expect(() => deriveAmbientTheme(systemState)).not.toThrow();
        },
      ),
      { numRuns: 100 },
    );
  });
});
