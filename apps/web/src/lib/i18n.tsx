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
