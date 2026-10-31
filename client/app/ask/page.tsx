"use client";
import { Database, CloudSun, FileText, Loader2, Mic, Send, Satellite, Store } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useApp } from "@/components/Shell";
import { Button, Chip, ErrorBanner, Note } from "@/components/ui";
import { api, AskResult, Entry, Source } from "@/lib/api";
import { inr, num, shortDate } from "@/lib/format";
import { CATEGORY_LABEL, useLang } from "@/lib/i18n";

const SUGGEST = {
  en: ["Fertiliser this season vs last?", "Cost per quintal on plot 2?", "Can I spray tomorrow?",
       "Profit at today's price?", "Summarise this season", "Prepare my claim file"],
  hi: ["Is season vs pichhle season khad par kitna kharch hua?", "Plot 2 ki prati quintal lagat?",
       "Kya kal spray kar sakte hain?", "Aaj ke daam par munafa kitna?", "Is season ka hisaab batao", "Claim file taiyaar karo"],
};
const SRC_ICON: Record<string, any> = { ledger: Database, forecast: CloudSun, weather: CloudSun, mandi: Store,
  satellite: Satellite, event: FileText, benchmark: Database };

type Msg = { role: "user" | "bot"; text: string; result?: AskResult };

export default function AskPage() {
  const { t, lang } = useLang();
  const { toast } = useApp();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [opened, setOpened] = useState<{ label: string; entries: Entry[] } | null>(null);
  const [packBusy, setPackBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, busy]);

  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    setError(null);
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setQ("");
    setBusy(true);
    try {
      const r = await api<AskResult>("/api/agent/ask", { method: "POST", json: { question } });
      setMsgs((m) => [...m, { role: "bot", text: r.answer, result: r }]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const voice = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return setError(t("voiceUnavailable"));
    const rec = new SR();
    rec.lang = lang === "hi" ? "hi-IN" : "en-IN";
    rec.onresult = (e: any) => setQ(e.results[0][0].transcript);
    rec.start();
  };

  const openSource = async (s: Source) => {
    if (s.type !== "ledger" || !Array.isArray(s.ref) || !s.ref.length) return;
    const r = await api<{ entries: Entry[] }>(`/api/entries?ids=${s.ref.join(",")}`);
    setOpened({ label: s.label, entries: r.entries });
  };

  const generate = async (eventId: string) => {
    setPackBusy(true);
    try {
      const out = await api<{ file_url: string }>(`/api/events/${eventId}/evidence-pack`, { method: "POST" });
      toast(lang === "hi" ? "सबूत PDF तैयार" : "Evidence pack ready");
      window.open(out.file_url, "_blank");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPackBusy(false);
    }
  };

  const verdictTone = { ok: "green", not_advised: "red", caution: "amber" } as const;
  const verdictText = {
    ok: lang === "hi" ? "छिड़काव ठीक" : "OK to spray",
    not_advised: lang === "hi" ? "छिड़काव न करें" : "Not advised",
    caution: lang === "hi" ? "सावधानी" : "Caution",
  };

  return (
    <div className="flex flex-col min-h-[calc(100vh-190px)]">
      <h1 className="text-[24px] font-extrabold mb-3">{t("ask")}</h1>
      <div className="flex-1 space-y-3">
        {msgs.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {SUGGEST[lang].map((s) => (
              <button key={s} onClick={() => ask(s)}
                className="rounded-full border border-line bg-white px-3.5 py-2 text-[15px] text-left min-h-[44px]">{s}</button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => m.role === "user" ? (
          <div key={i} className="ml-10 rounded-card rounded-br-md bg-primary text-white p-3">{m.text}</div>
        ) : (
          <div key={i} className="mr-6 rounded-card rounded-bl-md bg-white border border-line p-3">
            {m.result?.spray && (
              <div className="mb-2"><Chip tone={verdictTone[m.result.spray.verdict]}>{verdictText[m.result.spray.verdict]}</Chip></div>
            )}
            <p className="whitespace-pre-line">{m.text}</p>
            {m.result?.notice && <p className="mt-2 text-[13px] text-warn">{m.result.notice}</p>}
            {m.result?.pending_action?.type === "generate_evidence_pack" && (
              <Button className="mt-3 w-full" disabled={packBusy} onClick={() => generate(m.result!.pending_action!.event_id)}>
                <FileText size={18} />{t("generate")}
              </Button>
            )}
            {!!m.result?.sources.length && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {m.result.sources.map((s, j) => {
                  const Icon = SRC_ICON[s.type] || Database;
                  return (
                    <button key={j} onClick={() => openSource(s)}
                      className="inline-flex items-center gap-1 rounded-full bg-paper border border-line px-2.5 py-1 text-[12px] text-muted">
                      <Icon size={13} />{s.label}{s.mode === "cached" ? " · cached" : ""}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="mr-6 rounded-card bg-white border border-line p-3 text-muted inline-flex items-center gap-2"><Loader2 className="animate-spin" size={18} />{t("checking")}</div>}
        <ErrorBanner key={error || ""} message={error} onClose={() => setError(null)} />
        {opened && (
          <Note tone="grey">
            <div className="flex justify-between font-semibold mb-1"><span>{opened.label}</span><button onClick={() => setOpened(null)}>×</button></div>
            {opened.entries.map((e) => (
              <div key={e.entry_id} className="flex justify-between text-[14px] py-0.5">
                <span>{shortDate(e.entry_date, lang)} · {e.item || CATEGORY_LABEL[e.category]?.[lang]}{e.quantity !== null ? ` (${num(e.quantity)} ${e.unit})` : ""}</span>
                <b>{e.cost_inr !== null ? inr(e.cost_inr) : ""}</b>
              </div>
            ))}
          </Note>
        )}
        <div ref={end} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); ask(q); }}
        className="sticky bottom-[72px] mt-3 flex gap-2 bg-paper py-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} maxLength={300} placeholder={t("askPlaceholder")}
          className="flex-1 min-h-[48px] rounded-xl border border-line bg-white px-3 outline-none" />
        <button type="button" onClick={voice} aria-label="Voice" className="h-12 w-12 rounded-xl border border-line bg-white grid place-items-center"><Mic /></button>
        <button type="submit" aria-label="Send" disabled={busy || !q.trim()} className="h-12 w-12 rounded-xl bg-primary text-white grid place-items-center disabled:opacity-50"><Send /></button>
      </form>
    </div>
  );
}
