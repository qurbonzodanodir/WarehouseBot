"use client";

import React, { createContext, useContext, useState, useSyncExternalStore } from "react";
import { ru } from "./ru";
import { tj } from "./tj";

type LangType = "ru" | "tj";

interface TranslationObject {
  [key: string]: TranslationValue;
}
type TranslationValue = string | TranslationObject;

function subscribe() {
  return () => {};
}

function getStoredLanguage(): LangType {
  if (typeof window === "undefined") return "ru";
  const saved = localStorage.getItem("wh_lang");
  return saved === "ru" || saved === "tj" ? saved : "ru";
}

function getNestedValue(obj: TranslationValue, path: string): string | undefined {
  let current: TranslationValue | undefined = obj;

  for (const part of path.split(".")) {
    if (!current || typeof current === "string") {
      return undefined;
    }
    current = current[part];
  }

  return typeof current === "string" ? current : undefined;
}

interface LanguageContextProps {
  lang: LangType;
  setLang: (lang: LangType) => void;
  t: (key: string, variables?: Record<string, string | number>) => string;
}

const LanguageContext = createContext<LanguageContextProps>({
  lang: "ru",
  setLang: () => {},
  t: (k) => k,
});

export const LanguageProvider = ({ children }: { children: React.ReactNode }) => {
  const [lang, setLangState] = useState<LangType>(getStoredLanguage);
  const mounted = useSyncExternalStore(subscribe, () => true, () => false);

  const setLang = (nextLang: LangType) => {
    setLangState(nextLang);
    localStorage.setItem("wh_lang", nextLang);
  };

  const t = (key: string, variables?: Record<string, string | number>): string => {
    const dict = lang === "tj" ? tj : ru;
    let template = getNestedValue(dict, key);
    if (!template) {
      // Fallback
      template = getNestedValue(ru, key) || key;
    }

    if (typeof template === "string" && variables) {
      return Object.keys(variables).reduce((str, varName) => {
        return str.replace(new RegExp(`{${varName}}`, "g"), String(variables[varName]));
      }, template);
    }

    return template;
  };

  if (!mounted) {
    // Prevent SSR hydration mismatch
    return null;
  }

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useTranslation = () => useContext(LanguageContext);
