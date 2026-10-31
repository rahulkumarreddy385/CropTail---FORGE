"use client";
import { createContext, useContext, useEffect, useState } from "react";

export type Lang = "hi" | "en";

const STRINGS = {
  home: { hi: "होम", en: "Home" },
  log: { hi: "दर्ज करें", en: "Log" },
  ledger: { hi: "खाता", en: "Ledger" },
  ask: { hi: "पूछें", en: "Ask" },
  alerts: { hi: "अलर्ट", en: "Alerts" },
  greeting: { hi: "नमस्ते", en: "Namaste" },
  demoMode: { hi: "डेमो मोड", en: "Demo mode" },
  cached: { hi: "कैश्ड", en: "cached" },
  synthetic: { hi: "नमूना डेटा", en: "sample data" },
  yesDamaged: { hi: "हाँ, नुकसान हुआ", en: "Yes, damaged" },
  no: { hi: "नहीं", en: "No" },
  reportWithin: { hi: "रिपोर्ट करने का समय बाकी", en: "Report within" },
  createPack: { hi: "सबूत (PDF) बनाएँ", en: "Create evidence pack" },
  seasonCost: { hi: "इस सीज़न का खर्च", en: "Season cost" },
  lastLog: { hi: "आखिरी एंट्री", en: "Last log" },
  daysAgo: { hi: "दिन पहले", en: "days ago" },
  today: { hi: "आज", en: "today" },
  addFirstPlot: { hi: "अपना पहला खेत जोड़ें", en: "Add your first plot" },
  managePlots: { hi: "खेत और सीज़न", en: "Plots & seasons" },
  risk_low: { hi: "कम जोखिम", en: "Low risk" },
  risk_medium: { hi: "मध्यम जोखिम", en: "Medium risk" },
  risk_high: { hi: "ज़्यादा जोखिम", en: "High risk" },
  logPlaceholder: { hi: "जैसे: Plot 2 mein 2 bag urea dala, ₹900", en: "e.g. Plot 2 mein 2 bag urea dala, ₹900" },
  parse: { hi: "पढ़ें", en: "Parse" },
  confirm: { hi: "पक्का करें", en: "Confirm" },
  cancel: { hi: "रद्द करें", en: "Cancel" },
  savedTo: { hi: "सेव हुआ:", en: "Saved to" },
  whichPlot: { hi: "कौन सा खेत?", en: "Which plot?" },
  voiceUnavailable: { hi: "आवाज़ उपलब्ध नहीं, कृपया लिखें।", en: "Voice not available, please type." },
  listening: { hi: "सुन रहा हूँ...", en: "Listening..." },
  checkFields: { hi: "कृपया पीले फ़ील्ड जाँचें", en: "Please check the highlighted fields" },
  date: { hi: "तारीख", en: "Date" },
  plot: { hi: "खेत", en: "Plot" },
  category: { hi: "श्रेणी", en: "Category" },
  item: { hi: "चीज़", en: "Item" },
  quantity: { hi: "मात्रा", en: "Quantity" },
  cost: { hi: "खर्च (₹)", en: "Cost (₹)" },
  totalCost: { hi: "कुल खर्च", en: "Total cost" },
  harvest: { hi: "उपज", en: "Harvest" },
  costPerQ: { hi: "प्रति क्विंटल लागत", en: "Cost per quintal" },
  profit: { hi: "मुनाफा", en: "Profit" },
  projectedProfit: { hi: "अनुमानित मुनाफा", en: "Projected profit" },
  costByCategory: { hi: "श्रेणी अनुसार खर्च", en: "Cost by category" },
  timeline: { hi: "रिकॉर्ड", en: "Timeline" },
  nothingLogged: { hi: "अभी कुछ दर्ज नहीं। पहली एंट्री के लिए + दबाएँ।", en: "Nothing logged yet. Tap + Log to add your first activity." },
  addHarvest: { hi: "प्रति क्विंटल लागत देखने के लिए उपज दर्ज करें।", en: "Add your harvest quantity to see cost per quintal." },
  cropHealth: { hi: "फसल की हरियाली (सैटेलाइट NDVI)", en: "Crop health (satellite NDVI)" },
  mandiPrice: { hi: "मंडी भाव", en: "Mandi price" },
  askPlaceholder: { hi: "अपने खेत के बारे में पूछें...", en: "Ask about your farm..." },
  checking: { hi: "आपके रिकॉर्ड देख रहा हूँ...", en: "Checking your records..." },
  generate: { hi: "PDF बनाएँ", en: "Generate" },
  noAlerts: { hi: "कोई मौसम अलर्ट नहीं। हम हर 6 घंटे में आपके खेत जाँचते हैं।", en: "No weather alerts. We check your plots every 6 hours." },
  runCheck: { hi: "अभी मौसम जाँचें", en: "Run weather check" },
  reportLoss: { hi: "नुकसान दर्ज करें", en: "Report a loss" },
  addPhoto: { hi: "फोटो जोड़ें", en: "Add photo" },
  lossEstimate: { hi: "अनुमानित नुकसान (क्विंटल)", en: "Estimated loss (quintals)" },
  notes: { hi: "नोट", en: "Notes" },
  save: { hi: "सेव करें", en: "Save" },
  open: { hi: "खोलें", en: "Open" },
  windowPassed: {
    hi: "रिपोर्ट का समय निकल गया। रिकॉर्ड अब भी बना सकते हैं, पर सीधे बीमा कंपनी या कृषि विभाग से संपर्क करें।",
    en: "Reporting window passed. You can still generate the record, but contact your insurer or agriculture office directly.",
  },
  cantConnect: { hi: "CropTrail से जुड़ नहीं पा रहे। इंटरनेट जाँचें और दोबारा कोशिश करें।", en: "Can't connect to CropTrail. Check your internet and try again." },
  retry: { hi: "फिर कोशिश करें", en: "Retry" },
  duplicate: { hi: "यह अभी सेव की गई एंट्री जैसा लगता है। फिर भी सेव करें?", en: "This looks like a duplicate of an entry you just saved. Save anyway?" },
  saveAnyway: { hi: "फिर भी सेव करें", en: "Save anyway" },
} as const;

export type Key = keyof typeof STRINGS;

const LangCtx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: (k: Key) => string }>({
  lang: "hi",
  setLang: () => {},
  t: (k) => STRINGS[k].en,
});

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("hi");
  useEffect(() => {
    try {
      const saved = localStorage.getItem("croptrail-lang");
      if (saved === "en" || saved === "hi") setLangState(saved);
    } catch {}
  }, []);
  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("croptrail-lang", l);
    } catch {}
  };
  const t = (k: Key) => STRINGS[k][lang];
  return <LangCtx.Provider value={{ lang, setLang, t }}>{children}</LangCtx.Provider>;
}

export const useLang = () => useContext(LangCtx);

export const CATEGORY_LABEL: Record<string, { hi: string; en: string }> = {
  sowing: { hi: "बुवाई", en: "Sowing" }, seed: { hi: "बीज", en: "Seed" }, land_prep: { hi: "जुताई/तैयारी", en: "Land prep" },
  fertiliser: { hi: "खाद", en: "Fertiliser" }, pesticide: { hi: "दवा/छिड़काव", en: "Pesticide" },
  labour: { hi: "मजदूरी", en: "Labour" }, irrigation: { hi: "सिंचाई", en: "Irrigation" },
  harvest: { hi: "उपज", en: "Harvest" }, sale: { hi: "बिक्री", en: "Sale" }, note: { hi: "नोट", en: "Note" },
};
export const STAGE_LABEL: Record<string, { hi: string; en: string }> = {
  vegetative: { hi: "बढ़वार", en: "vegetative" }, flowering: { hi: "फूल", en: "flowering" },
  fruiting: { hi: "फल", en: "fruiting" }, maturity: { hi: "पकाव", en: "maturity" },
  harvest_ready: { hi: "कटाई योग्य", en: "harvest ready" }, unknown: { hi: "अज्ञात", en: "unknown" },
};
export const CROP_LABEL: Record<string, { hi: string; en: string }> = {
  paddy: { hi: "धान", en: "Paddy" }, wheat: { hi: "गेहूँ", en: "Wheat" }, tomato: { hi: "टमाटर", en: "Tomato" },
  other: { hi: "अन्य", en: "Other" },
};
export const EVENT_LABEL: Record<string, { hi: string; en: string }> = {
  hail: { hi: "ओलावृष्टि", en: "Hail" }, inundation: { hi: "जलभराव", en: "Inundation" },
  cloudburst: { hi: "बादल फटना", en: "Cloudburst" }, landslide: { hi: "भूस्खलन", en: "Landslide" },
  natural_fire: { hi: "आग", en: "Natural fire" },
  unseasonal_rain_post_harvest: { hi: "कटाई के बाद बेमौसम बारिश", en: "Unseasonal rain after harvest" },
  other: { hi: "अन्य", en: "Other" },
};
