import { expect, test } from "@playwright/test";
import { DEFAULT_RULES, newTracker, step } from "../src/components/lab/activity";
import type { Frame, Tracker } from "../src/components/lab/activity";

const run = (frames: Frame[]): Tracker => frames.reduce((tr, f) => step(tr, f), newTracker(0));
const every = (from: number, to: number, f: Omit<Frame, "t">): Frame[] =>
  Array.from({ length: Math.round((to - from) * 5) }, (_, i) => ({ t: from + (i + 1) / 5, ...f }));

test("lab activity rules: working, idle, phone, away, with totals", () => {
  const working = every(0, 4, { person: 0.9, phone: 0, motion: 10 });
  const still = every(4, 16, { person: 0.9, phone: 0, motion: 0 });
  const phone = every(16, 21, { person: 0.9, phone: 0.8, motion: 0 });
  const gone = every(21, 30, { person: 0, phone: 0, motion: 0 });
  const tr = run([...working, ...still, ...phone, ...gone]);

  expect(tr.changes.map((c) => c.to)).toEqual(["working", "idle", "phone_use", "away"]);
  expect(tr.changes[1].t).toBeCloseTo(4 + DEFAULT_RULES.idleAfterS, 0); // idle only after the still period
  expect(tr.phoneEvents).toHaveLength(1);
  expect(tr.phoneEvents[0].confidence).toBeCloseTo(0.8);
  expect(tr.inViewS).toBeCloseTo(21, 0);
  expect(Object.values(tr.totals).reduce((a, b) => a + b, 0)).toBeCloseTo(30, 0);
});

test("lab activity rules: a short absence keeps the state, a stalled tab books at most 1 s", () => {
  const tr = run([
    ...every(0, 2, { person: 0.9, phone: 0, motion: 10 }),
    ...every(2, 4, { person: 0, phone: 0, motion: 0 }), // 2 s gap < awayAfterS
    { t: 60, person: 0.9, phone: 0, motion: 10 }, // tab was in the background for ~56 s
  ]);
  expect(tr.state).toBe("working");
  expect(tr.totals.working).toBeLessThan(6);
});
