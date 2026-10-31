"use client";
import { Bell, BookOpen, Home, MessageCircle, PlusCircle, WifiOff } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, Health, onConnectivity } from "@/lib/api";
import { LangProvider, useLang } from "@/lib/i18n";
import { Button } from "./ui";

type AppCtx = { health: Health | null; suspected: number; refreshBadges: () => void; toast: (msg: string) => void };
const Ctx = createContext<AppCtx>({ health: null, suspected: 0, refreshBadges: () => {}, toast: () => {} });
export const useApp = () => useContext(Ctx);

function Inner({ children }: { children: React.ReactNode }) {
  const { t, lang, setLang } = useLang();
  const path = usePathname();
  const [health, setHealth] = useState<Health | null>(null);
  const [down, setDown] = useState(false);
  const [suspected, setSuspected] = useState(0);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const refreshBadges = useCallback(() => {
    api<any[]>("/api/events?status=suspected").then((e) => setSuspected(e.length)).catch(() => {});
  }, []);
  const load = useCallback(() => {
    api<Health>("/api/health").then(setHealth).catch(() => {});
    refreshBadges();
  }, [refreshBadges]);

  useEffect(() => {
    load();
    return onConnectivity(setDown) as unknown as () => void;
  }, [load]);
  useEffect(() => {
    refreshBadges();
  }, [path, refreshBadges]);

  const toast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 2600);
  };

  const tabs = [
    { href: "/", icon: Home, label: t("home") },
    { href: "/log", icon: PlusCircle, label: t("log") },
    { href: "/ledger", icon: BookOpen, label: t("ledger") },
    { href: "/ask", icon: MessageCircle, label: t("ask") },
    { href: "/alerts", icon: Bell, label: t("alerts"), badge: suspected },
  ];
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));

  return (
    <Ctx.Provider value={{ health, suspected, refreshBadges, toast }}>
      <header className="sticky top-0 z-20 bg-paper/95 backdrop-blur border-b border-line">
        <div className="mx-auto max-w-[560px] px-4 h-14 flex items-center gap-2">
          <Link href="/" className="flex items-center gap-2 font-extrabold text-[19px] text-primary">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M7 20c0-6 3-10 10-12" /><path d="M7 20c-2-3-2-7 1-10 2 3 2 7-1 10z" /><path d="M3 20h18" />
            </svg>
            CropTrail
          </Link>
          <div className="flex-1" />
          {health?.llm === "fallback" && (
            <span className="rounded-full bg-[#E4E1D8] text-muted text-[12px] font-semibold px-2.5 py-1">{t("demoMode")}</span>
          )}
          <button onClick={() => setLang(lang === "hi" ? "en" : "hi")}
            className="min-h-[40px] rounded-full border border-line bg-white px-3 text-[14px] font-semibold" aria-label="Switch language">
            {lang === "hi" ? "English" : "हिंदी"}
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-[560px] px-4 pt-4 pb-28">{children}</main>

      {toastMsg && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-40 rounded-full bg-ink text-white px-4 py-2.5 text-[15px] shadow-lg max-w-[90vw]">
          {toastMsg}
        </div>
      )}

      <nav className="fixed bottom-0 inset-x-0 z-30 bg-white border-t border-line pb-[env(safe-area-inset-bottom)]">
        <div className="mx-auto max-w-[560px] grid grid-cols-5">
          {tabs.map(({ href, icon: Icon, label, badge }) => (
            <Link key={href} href={href}
              className={`relative flex flex-col items-center justify-center min-h-[62px] text-[12px] font-semibold ${active(href) ? "text-primary" : "text-muted"}`}>
              <Icon size={24} strokeWidth={active(href) ? 2.4 : 1.8} />
              <span className="mt-0.5">{label}</span>
              {!!badge && (
                <span className="absolute top-1.5 left-1/2 ml-2 min-w-[20px] h-5 rounded-full bg-warn text-white text-[12px] px-1.5 grid place-items-center">
                  {badge}
                </span>
              )}
            </Link>
          ))}
        </div>
      </nav>

      {down && (
        <div className="fixed inset-0 z-50 bg-paper grid place-items-center p-6">
          <div className="text-center max-w-xs">
            <WifiOff size={48} className="mx-auto text-muted" />
            <p className="mt-4 text-[18px] font-semibold">{t("cantConnect")}</p>
            <Button className="mt-6 w-full" onClick={() => { setDown(false); load(); window.location.reload(); }}>{t("retry")}</Button>
          </div>
        </div>
      )}
    </Ctx.Provider>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  return (
    <LangProvider>
      <Inner>{children}</Inner>
    </LangProvider>
  );
}
