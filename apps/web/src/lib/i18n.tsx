"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type Locale = "en" | "bn";

const DICT = {
  en: {
    overview: "Overview",
    liveFloor: "Live floor",
    reviewQueue: "Review queue",
    needles: "Needles",
    performance: "Performance",
    cameras: "Cameras",
    liveCameras: "Live cameras",
    lab: "Lab",
    noAccess: "Your role cannot open this page",
    noAccessText: "Ask a factory admin if you need it.",
    setup: "Setup",
    alerts: "Alerts",
    settings: "Settings",
    logOut: "Log out",
    running: "Running",
    idle: "Idle",
    down: "Machine down",
    noData: "No data",
    break: "Break",
    output: "Output",
    target: "Target",
    efficiency: "SMV efficiency",
    openAlerts: "Open alerts",
    confirm: "Confirm",
    reject: "Reject",
    acknowledge: "Acknowledge",
    resolve: "Resolve",
    updated: "updated",
    dayShift: "Shift",
    stations: "stations",
    loading: "Loading…",
    retry: "Try again",
  },
  bn: {
    overview: "সারসংক্ষেপ",
    liveFloor: "লাইভ ফ্লোর",
    reviewQueue: "যাচাই তালিকা",
    needles: "সুই",
    performance: "কর্মদক্ষতা",
    cameras: "ক্যামেরা",
    liveCameras: "লাইভ ক্যামেরা",
    lab: "ল্যাব",
    noAccess: "আপনার ভূমিকায় এই পাতা খোলা যায় না",
    noAccessText: "দরকার হলে ফ্যাক্টরি অ্যাডমিনকে বলুন।",
    setup: "সেটআপ",
    alerts: "সতর্কতা",
    settings: "সেটিংস",
    logOut: "লগ আউট",
    running: "চলছে",
    idle: "অলস",
    down: "মেশিন বন্ধ",
    noData: "তথ্য নেই",
    break: "বিরতি",
    output: "উৎপাদন",
    target: "লক্ষ্য",
    efficiency: "SMV দক্ষতা",
    openAlerts: "খোলা সতর্কতা",
    confirm: "নিশ্চিত",
    reject: "বাতিল",
    acknowledge: "স্বীকার",
    resolve: "সমাধান",
    updated: "হালনাগাদ",
    dayShift: "শিফট",
    stations: "স্টেশন",
    loading: "লোড হচ্ছে…",
    retry: "আবার চেষ্টা করুন",
  },
} as const;

const BN_TEXT: Record<string, string> = {
  "Acknowledged": "স্বীকৃত",
  "Alert center": "সতর্কতা কেন্দ্র",
  "Alert rules": "সতর্কতার নিয়ম",
  "Alerts": "সতর্কতা",
  "All alerts": "সব সতর্কতা",
  "Breaks": "ভাঙা",
  "Confirmed units": "নিশ্চিত ইউনিট",
  "Critical": "জরুরি",
  "Devices": "ডিভাইস",
  "Efficiency": "দক্ষতা",
  "Factory simulator": "কারখানা সিমুলেটর",
  "Info": "তথ্য",
  "Issued": "দেওয়া হয়েছে",
  "Line": "লাইন",
  "Lines": "লাইনসমূহ",
  "Log in": "লগ ইন",
  "Lot": "লট",
  "No open alerts. The floor is quiet.": "কোনো খোলা সতর্কতা নেই। ফ্লোর শান্ত।",
  "None": "নেই",
  "Open queue": "তালিকা খুলুন",
  "Output / target": "উৎপাদন / লক্ষ্য",
  "Output by hour": "ঘণ্টাভিত্তিক উৎপাদন",
  "Pattern": "ধরন",
  "Rate": "হার",
  "Staff accounts only. Ask your factory admin for access.": "শুধু কর্মকর্তাদের অ্যাকাউন্ট। প্রবেশাধিকারের জন্য কারখানার অ্যাডমিনকে বলুন।",
  "Stations": "স্টেশন",
  "Target pace": "লক্ষ্যের গতি",
  "Warning": "সতর্কবার্তা",
  "Email": "ইমেইল",
  "Password": "পাসওয়ার্ড",
  "Needles": "সুই",
  "Settings": "সেটিংস",
  "No alerts here": "এখানে কোনো সতর্কতা নেই",
  "Confirmed breaks only. A lot is judged after at least 10 needles and 50 running hours.": "শুধু নিশ্চিত ভাঙা গণনা হয়। অন্তত ১০টি সুই ও ৫০ ঘণ্টা চলার পরে লট বিচার করা হয়।",
  "Every alert from every line. Rules and thresholds are edited in Settings.": "সব লাইনের সব সতর্কতা। নিয়ম ও সীমা সেটিংসে বদলানো যায়।",
  "Phone use, needle breaks and low-confidence events wait here. Nothing counts toward a person's numbers until it is reviewed.": "ফোন ব্যবহার, সুই ভাঙা ও অনিশ্চিত ঘটনা এখানে অপেক্ষা করে। যাচাই না হওয়া পর্যন্ত কিছুই কারও হিসাবে গণনা হয় না।",
  "Nothing to review": "যাচাই করার কিছু নেই",
  "Events the system is unsure about will wait here for a person to decide.": "যেসব ঘটনায় সিস্টেম নিশ্চিত নয়, সেগুলো এখানে একজন মানুষের সিদ্ধান্তের অপেক্ষায় থাকবে।",
  "When a rule fires it shows up here and on the overview.": "কোনো নিয়ম চালু হলে তা এখানে ও সারসংক্ষেপে দেখা যাবে।",
  "Lots by breaks per 1,000 running hours": "প্রতি ১,০০০ ঘণ্টায় ভাঙা অনুযায়ী লট",
  "Stations running": "চলমান স্টেশন",
  "Cameras": "ক্যামেরা",
  "Machine sensors": "মেশিন সেন্সর",
  "Edge boxes": "এজ বক্স",
  "Card readers": "কার্ড রিডার",
  "Worker": "কর্মী",
  "Machine": "মেশিন",
  "Severity": "গুরুত্ব",
  "On": "চালু",
  "Save": "সংরক্ষণ",
  "Saved": "সংরক্ষিত",
  "Batch pattern": "ব্যাচ সমস্যা",
  "One machine": "একটি মেশিন",
  "One worker": "একজন কর্মী",
  "Normal": "স্বাভাবিক",
  "Too little use": "যথেষ্ট ব্যবহার হয়নি",
  "All": "সব",
  "Active": "সক্রিয়",
  "Resolved": "সমাধান হয়েছে",
  "Only a factory admin can change these.": "শুধু কারখানার অ্যাডমিন এগুলো বদলাতে পারেন।",
  "Alert rules apply to the whole factory. Every change is logged.": "সতর্কতার নিয়ম পুরো কারখানায় প্রযোজ্য। প্রতিটি পরিবর্তন লগ করা হয়।"
};

export type MessageKey = keyof (typeof DICT)["en"];

type Ctx = { locale: Locale; setLocale: (l: Locale) => void; t: (k: MessageKey) => string };
const I18nContext = createContext<Ctx | null>(null);
const STORAGE_KEY = "ss-locale";

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved === "en" || saved === "bn") setLocaleState(saved);
    } catch {
      /* storage blocked: stay on English */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* storage blocked: choice lasts for this page only */
    }
  }, []);

  const value = useMemo<Ctx>(() => ({ locale, setLocale, t: (k) => DICT[locale][k] }), [locale, setLocale]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside I18nProvider");
  return ctx;
}

/** Translate an English UI string (falls back to English when no Bangla text exists). */
export function useTr(): (text: string) => string {
  const { locale } = useI18n();
  return (text) => (locale === "bn" ? BN_TEXT[text] ?? text : text);
}

/** `<T>Alert center</T>` renders the string in the current language. */
export function T({ children }: { children: string }) {
  const tr = useTr();
  return <>{tr(children)}</>;
}
