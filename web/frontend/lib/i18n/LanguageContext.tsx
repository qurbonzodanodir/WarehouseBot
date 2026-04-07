"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { ru } from "./ru";
import { tj } from "./tj";

type LangType = "ru" | "tj";

type Translations = typeof ru;

const getNestedValue = (obj: any, path: string) => {
  return path.split(".").reduce((acc, part) => acc && acc[part], obj);
};

interface LanguageContextProps {
  lang: LangType;
  setLang: (l: LangType) => void;
  t: (key: string, variables?: Record<string, any>) => string;
}

const LanguageContext = createContext<LanguageContextProps>({
  lang: "ru",
  setLang: () => {},
  t: (k) => k,
});

export const LanguageProvider = ({ children }: { children: React.ReactNode }) => {
  const [lang, setLangState] = useState<LangType>("ru");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("wh_lang") as LangType;
    if (saved === "ru" || saved === "tj") {
      setLangState(saved);
    }
    setMounted(true);
  }, []);

  const setLang = (l: LangType) => {
    setLangState(l);
    localStorage.setItem("wh_lang", l);
  };

  const t = (key: string, variables?: Record<string, any>): string => {
    const dict = lang === "tj" ? tj : ru;
    let template = getNestedValue(dict, key);
    if (!template) {
      // Fallback
      template = getNestedValue(ru, key) || key;
    }
    
    if (typeof template === "string" && variables) {
      return Object.keys(variables).reduce((str, varName) => {
        return str.replace(new RegExp(`{${varName}}`, "g"), variables[varName]);
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
