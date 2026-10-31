"use client";
import { CloudRain, Loader2, RefreshCw } from "lucide-react";
import { EVENT_ICON } from "@/components/eventIcons";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useApp } from "@/components/Shell";
import { Button, Card, Chip, ErrorBanner, Field, inputCls, Note, SectionTitle, Skeleton } from "@/components/ui";
import { api, EventT, Plot } from "@/lib/api";
import { countdown, shortDate } from "@/lib/format";
import { EVENT_LABEL, useLang } from "@/lib/i18n";

const STATUS_TONE = { suspected: "amber", confirmed: "blue", dismissed: "grey" } as const;

export default function AlertsPage() {
  const { t, lang } = useLang();
  const { health, refreshBadges, toast } = useApp();
  const router = useRouter();
  const [events, setEvents] = useState<EventT[] | null>(null);
  const [plots, setPlots] = useState<Plot[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [report, setReport] = useState({ plot_id: "", type: "hail", event_date: "", notes: "", loss: "" });
  const [sim, setSim] = useState({ plot_id: "", mm: "78.4", date: "" });

  const load = useCallback(() => {
    api<EventT[]>("/api/events").then(setEvents).catch((e) => setError(e.message));
    refreshBadges();
  }, [refreshBadges]);
  useEffect(() => {
    load();
    api<Plot[]>("/api/plots?include_risk=false").then((ps) => {
      setPlots(ps);
      const today = new Date().toISOString().slice(0, 10);
      setReport((r) => ({ ...r, plot_id: ps[0]?.plot_id || "", event_date: today }));
      setSim((s) => ({ ...s, plot_id: ps[0]?.plot_id || "", date: today }));
    });
  }, [load]);

  const runCheck = async (simulate?: boolean) => {
    setRunning(true);
    setError(null);
    try {
      const body = simulate ? { simulate: { plot_id: sim.plot_id, date: sim.date, precipitation_mm: Number(sim.mm) } } : {};
      const out = await api<any>("/api/monitor/run", { method: "POST", json: body });
      toast(out.new_events.length
        ? (lang === "hi" ? `${out.new_events.length} नया अलर्ट` : `${out.new_events.length} new alert(s)`)
        : (lang === "hi" ? "कोई नया अलर्ट नहीं" : "No new alerts"));
      if (out.errors?.length) setError(out.errors[0].message);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };

  const submitReport = async () => {
    setError(null);
    try {
      const ev = await api<EventT>("/api/events", { method: "POST", json: {
        plot_id: report.plot_id, type: report.type, event_date: report.event_date,
        farmer_notes: report.notes || null, estimated_loss_quintals: report.loss === "" ? null : Number(report.loss),
      } });
      router.push(`/alerts/${ev.event_id}`);
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="space-y-3">
      <h1 className="text-[24px] font-extrabold">{t("alerts")}</h1>
      <ErrorBanner key={error || ""} message={error} onClose={() => setError(null)} />
      {events === null && <><Skeleton /><Skeleton /></>}
      {events?.length === 0 && <Note tone="grey">{t("noAlerts")}</Note>}
      {events?.map((e) => {
        const Icon = EVENT_ICON[e.type] || CloudRain;
        return (
          <Card key={e.event_id} onClick={() => router.push(`/alerts/${e.event_id}`)}>
            <div className="flex gap-3">
              <span className="h-11 w-11 shrink-0 rounded-xl bg-info-soft text-info grid place-items-center"><Icon /></span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-bold">{EVENT_LABEL[e.type]?.[lang]}</p>
                  <Chip tone={STATUS_TONE[e.status]}>{e.status}</Chip>
                </div>
                <p className="text-[14px] text-muted">{e.plot_name} · {shortDate(e.event_date, lang)}</p>
                <p className="text-[14px] mt-1">{e.trigger_detail}</p>
                {e.status === "confirmed" && (
                  <p className={`text-[14px] font-semibold mt-1 ${e.past_deadline ? "text-danger" : "text-info"}`}>
                    {e.past_deadline ? (lang === "hi" ? "रिपोर्ट का समय निकल गया" : "Reporting window passed")
                      : `${t("reportWithin")} ${countdown(e.seconds_left)}`}
                  </p>
                )}
              </div>
            </div>
          </Card>
        );
      })}

      <SectionTitle>{t("reportLoss")}</SectionTitle>
      {!showReport ? (
        <Button variant="secondary" className="w-full" onClick={() => setShowReport(true)}>{t("reportLoss")}</Button>
      ) : (
        <Card className="space-y-2">
          <Field label={t("plot")}>
            <select className={inputCls} value={report.plot_id} onChange={(e) => setReport({ ...report, plot_id: e.target.value })}>
              {plots.map((p) => <option key={p.plot_id} value={p.plot_id}>{p.name}</option>)}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label={lang === "hi" ? "प्रकार" : "Type"}>
              <select className={inputCls} value={report.type} onChange={(e) => setReport({ ...report, type: e.target.value })}>
                {Object.keys(EVENT_LABEL).map((k) => <option key={k} value={k}>{EVENT_LABEL[k][lang]}</option>)}
              </select>
            </Field>
            <Field label={t("date")}>
              <input type="date" className={inputCls} value={report.event_date} onChange={(e) => setReport({ ...report, event_date: e.target.value })} />
            </Field>
          </div>
          <Field label={t("lossEstimate")}>
            <input inputMode="decimal" className={inputCls} value={report.loss} onChange={(e) => setReport({ ...report, loss: e.target.value })} />
          </Field>
          <Field label={t("notes")}>
            <textarea maxLength={500} rows={2} className={inputCls} value={report.notes} onChange={(e) => setReport({ ...report, notes: e.target.value })} />
          </Field>
          <Button className="w-full" onClick={submitReport}>{t("save")}</Button>
        </Card>
      )}

      <SectionTitle>{lang === "hi" ? "डेमो ऑपरेटर" : "Demo operator"}</SectionTitle>
      <Button variant="secondary" className="w-full" disabled={running} onClick={() => runCheck(false)}>
        {running ? <Loader2 className="animate-spin" /> : <RefreshCw size={18} />}{t("runCheck")}
      </Button>
      {health?.simulation_allowed && (
        <Card className="space-y-2">
          <p className="text-[14px] text-muted">
            {lang === "hi" ? "रिहर्सल के लिए बारिश का सिमुलेशन। बनने वाला अलर्ट और PDF \"SIMULATED\" लिखा दिखाएगा।"
              : "Rehearsal only: simulate rainfall. The alert and PDF will be clearly marked SIMULATED."}
          </p>
          <div className="grid grid-cols-3 gap-2">
            <select className="rounded-lg border border-line px-2 min-h-[44px] bg-white" value={sim.plot_id} onChange={(e) => setSim({ ...sim, plot_id: e.target.value })}>
              {plots.map((p) => <option key={p.plot_id} value={p.plot_id}>{p.name}</option>)}
            </select>
            <input type="date" className="rounded-lg border border-line px-2 min-h-[44px] bg-white" value={sim.date} onChange={(e) => setSim({ ...sim, date: e.target.value })} />
            <input inputMode="decimal" className="rounded-lg border border-line px-2 min-h-[44px] bg-white" value={sim.mm} onChange={(e) => setSim({ ...sim, mm: e.target.value })} aria-label="Rain mm" />
          </div>
          <Button variant="secondary" className="w-full" disabled={running} onClick={() => runCheck(true)}>
            {lang === "hi" ? "बारिश सिमुलेट करें और जाँचें" : "Simulate rain and check"}
          </Button>
        </Card>
      )}
    </div>
  );
}
