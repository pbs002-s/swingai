/**
 * Lab-only activity rules for a test camera, a simplified browser port of edge/vision/rules.py.
 * No machine sensor and no work zone here, so "working" means a person is in view and moving.
 * Everything detected is a test signal for review, never a confirmed fact about a person.
 */

export type ActivityState = "working" | "idle" | "away" | "phone_use" | "uncertain";
export const STATES: ActivityState[] = ["working", "idle", "phone_use", "away", "uncertain"];

export type Rules = {
  awayAfterS: number; // no person this long -> away
  idleAfterS: number; // person present but still this long -> idle
  phoneMinS: number; // phone visible this long -> phone use (needs review)
  motionMin: number; // mean pixel change (0-255) that counts as movement
  personMin: number; // detector confidence for a person
  phoneMin: number; // detector confidence for a phone
};

export const DEFAULT_RULES: Rules = { awayAfterS: 5, idleAfterS: 10, phoneMinS: 3, motionMin: 3, personMin: 0.5, phoneMin: 0.4 };

/** One analysed frame. `t` is in seconds, `person`/`phone` are the best detector scores (0 when not seen). */
export type Frame = { t: number; person: number; phone: number; motion: number };

export type Change = { t: number; from: ActivityState; to: ActivityState };
export type PhoneEvent = { t: number; confidence: number };

export type Tracker = {
  startedAt: number;
  lastT: number;
  state: ActivityState;
  lastPersonAt: number;
  lastMotionAt: number;
  phoneSince: number | null;
  phoneBest: number;
  inViewS: number;
  totals: Record<ActivityState, number>;
  changes: Change[];
  phoneEvents: PhoneEvent[];
};

const MAX_STEP_S = 1; // a stalled tab must not book minutes to one state
const MAX_HISTORY = 200;

export function newTracker(t: number): Tracker {
  return {
    startedAt: t,
    lastT: t,
    state: "uncertain",
    lastPersonAt: t,
    lastMotionAt: t,
    phoneSince: null,
    phoneBest: 0,
    inViewS: 0,
    totals: { working: 0, idle: 0, away: 0, phone_use: 0, uncertain: 0 },
    changes: [],
    phoneEvents: [],
  };
}

function nextState(tr: Tracker, f: Frame, r: Rules, seen: boolean): ActivityState {
  if (!seen) return f.t - tr.lastPersonAt >= r.awayAfterS ? "away" : tr.state; // short gaps keep the state
  if (tr.phoneSince !== null && f.t - tr.phoneSince >= r.phoneMinS) return "phone_use";
  return f.t - tr.lastMotionAt < r.idleAfterS ? "working" : "idle";
}

/** Returns a new tracker after one frame; the input is not changed. */
export function step(tr: Tracker, f: Frame, r: Rules = DEFAULT_RULES): Tracker {
  const dt = Math.max(0, Math.min(f.t - tr.lastT, MAX_STEP_S));
  const seen = f.person >= r.personMin;
  const phone = seen && f.phone >= r.phoneMin;
  const base: Tracker = {
    ...tr,
    lastT: f.t,
    lastPersonAt: seen ? f.t : tr.lastPersonAt,
    lastMotionAt: seen && f.motion >= r.motionMin ? f.t : tr.lastMotionAt,
    phoneSince: phone ? (tr.phoneSince ?? f.t) : null,
    phoneBest: phone ? Math.max(tr.phoneBest, f.phone) : 0,
    inViewS: tr.inViewS + (seen ? dt : 0),
    totals: { ...tr.totals, [tr.state]: tr.totals[tr.state] + dt },
  };
  const state = nextState(base, f, r, seen);
  if (state === tr.state) return { ...base, state };
  return {
    ...base,
    state,
    changes: [...tr.changes, { t: f.t, from: tr.state, to: state }].slice(-MAX_HISTORY),
    phoneEvents: state === "phone_use" ? [...tr.phoneEvents, { t: f.t, confidence: base.phoneBest }].slice(-MAX_HISTORY) : tr.phoneEvents,
  };
}

/** Mean absolute change between two grayscale frames of equal size (0-255). */
export function motion(prev: Uint8ClampedArray | null, rgba: Uint8ClampedArray): { score: number; gray: Uint8ClampedArray } {
  const gray = new Uint8ClampedArray(rgba.length / 4);
  for (let i = 0; i < gray.length; i++) gray[i] = (rgba[i * 4] * 77 + rgba[i * 4 + 1] * 150 + rgba[i * 4 + 2] * 29) >> 8;
  if (!prev || prev.length !== gray.length) return { score: 0, gray };
  let sum = 0;
  for (let i = 0; i < gray.length; i++) sum += Math.abs(gray[i] - prev[i]);
  return { score: sum / gray.length, gray };
}
