"use client";
import { CloudRain, FileText, MapPin, Plus, Settings2, Sprout } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useApp } from "@/components/Shell";
import { Button, Card, Chip, ErrorBanner, ModeChip, Note, SectionTitle, Skeleton } from "@/components/ui";
import { api, ApiError, EventT, Plot } from "@/lib/api";
import { alertText, countdown, daysBetween, driverText, inr, longDate, shortDate } from "@/lib/format";
import { CROP_LABEL, STAGE_LABEL, useLang } from "@/lib/i18n";

export default function HomePage() {
  const { t, lang } = useLang();
  const { health, refreshBadges, toast } = useApp();
  const router = useRouter();
  const [farmer, setFarmer] = useState<any>(null);
  const [plots, setPlots] = useState<Plot[] | null>(null);
  const [events, setEvents] = useState<EventT[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    api("/api/farmer").then(setFarmer).catch(() => {});
    api<Plot[]>("/api/plots").then(setPlots).catch((e: ApiError) => setError(e.message));
    api<EventT[]>("/api/events").then(setEvents).catch(() => {});
  }, []);
  useEffect(load, [load]);

  const act = async (e: EventT, action: "confirm" | "dismiss") => {
    setBusy(e.event_id);
    try {
      await api(`/api/events/${e.event_id}`, { method: "PATCH", json: { action } });
      refreshBadges();
      if (action === "confirm") router.push(`/alerts/${e.event_id}`);
      else load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };

  const makePack = async (e: EventT) => {
    setBusy(e.event_id);
    try {
      const out = await api<{ file_url: string }>(`/api/events/${e.event_id}/evidence-pack`, { method: "POST" });
      toast(lang === "hi" ? "सबूत PDF तैयार" : "Evidence pack ready");
      window.open(out.file_url, "_blank");
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };

  const today = health?.today || new Date().toISOString().slice(0, 10);
  const suspected = events.filter((e) => e.status === "suspected");
  const open = events.filter((e) => e.status === "confirmed" && !e.past_deadline);
  const riskTone = (l?: string | null) => (l === "high" ? "red" : l === "medium" ? "amber" : "green");

  return (
    <div className="space-y-3">
      <div>
        <h1 className="text-[26px] font-extrabold leading-tight">
          {t("greeting")}{farmer ? `, ${farmer.name.split(" ")[0]}` : ""}
        </h1>
        <p className="text-muted">{longDate(today, lang)}</p>
      </div>

      <ErrorBanner message={error} onClose={() => setError(null)} />

        {health?.demo_seed_loaded && (
          <Note tone="amber">
            {lang === "hi"
              ? "डेमो प्रोफ़ाइल: किसान, खेत, हिसाब और नुकसान की घटना काल्पनिक हैं। यह दावा या आपके खेत का असली रिकॉर्ड नहीं है।"
              : "Demo profile: the farmer, plots, ledger and loss event are fictional. This is not your farm record or real claim evidence."}
          </Note>
        )}

        {suspected.map((e) => (
        <div key={e.event_id} className="rounded-card border-2 border-warn bg-warn-soft p-4">
          <div className="flex gap-2 items-start">
            <CloudRain className="text-warn shrink-0" />
            <p className="font-semibold">{alertText(e, lang)}</p>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Button disabled={busy === e.event_id} onClick={() => act(e, "confirm")}>{t("yesDamaged")}</Button>
            <Button variant="secondary" disabled={busy === e.event_id} onClick={() => act(e, "dismiss")}>{t("no")}</Button>
          </div>
        </div>
      ))}

      {open.map((e) => (
        <Card key={e.event_id} className="border-info">
          {e.is_demo && <Chip tone="amber" className="mb-2">{lang === "hi" ? "काल्पनिक डेमो" : "Fictional demo"}</Chip>}
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-[14px] text-muted">{e.plot_name} · {shortDate(e.event_date, lang)}</p>
              <p className="font-bold text-info text-[18px]">{t("reportWithin")} {countdown(e.seconds_left)}</p>
            </div>
            <FileText className="text-info" />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Button disabled={busy === e.event_id} onClick={() => makePack(e)}>{t("createPack")}</Button>
            <Button variant="secondary" onClick={() => router.push(`/alerts/${e.event_id}`)}>{t("open")}</Button>
          </div>
        </Card>
      ))}

      <SectionTitle right={<Link href="/plots" className="text-primary text-[14px] font-semibold inline-flex items-center gap-1"><Settings2 size={16} />{t("managePlots")}</Link>}>
        {lang === "hi" ? "मेरे खेत" : "My plots"}
      </SectionTitle>

      {plots === null && <><Skeleton /><Skeleton /></>}
      {plots?.length === 0 && (
        <Card className="text-center">
          <Sprout className="mx-auto text-primary" size={36} />
          <Button className="mt-3 w-full" onClick={() => router.push("/plots")}>{t("addFirstPlot")}</Button>
        </Card>
      )}
      {plots?.map((p) => {
        const s = p.active_season;
        const r = p.risk;
        const days = p.last_log_date ? daysBetween(p.last_log_date, today) : null;
        return (
          <Card key={p.plot_id} onClick={() => router.push(`/ledger?plot=${p.plot_id}`)}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <h3 className="text-[19px] font-bold">{p.name}</h3>
                <p className="text-[14px] text-muted inline-flex items-center gap-1"><MapPin size={14} />{p.area_acres} {lang === "hi" ? "एकड़" : "acres"}</p>
              </div>
              {r?.level && <Chip tone={riskTone(r.level)}>{t(`risk_${r.level}` as any)}</Chip>}
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {s && <Chip tone="green"><Sprout size={14} />{CROP_LABEL[s.crop]?.[lang]} · {STAGE_LABEL[p.stage?.stage || "unknown"]?.[lang]}</Chip>}
              <ModeChip mode={r?.mode} kind={r?.fixture_kind} />
            </div>
            {r?.drivers?.[0] && <p className="mt-2 text-[15px]">{driverText(r.drivers[0], lang)}</p>}
            {r?.error && <p className="mt-2 text-[14px] text-danger">{r.error}</p>}
            <div className="mt-3 flex justify-between text-[14px] text-muted">
              <span>{t("seasonCost")}: <b className="text-ink">{inr(p.season_cost)}</b></span>
              {days !== null && <span>{t("lastLog")}: {days === 0 ? t("today") : `${days} ${t("daysAgo")}`}</span>}
            </div>
          </Card>
        );
      })}

      {health?.sample_data_enabled && (
        <Note tone="amber">
          {lang === "hi"
            ? "डेमो नमूना डेटा चालू है; कुछ मौसम, उपग्रह या मंडी डेटा वास्तविक नहीं हो सकता।"
            : "Demo sample data is enabled; some weather, satellite or mandi data may be synthetic."}
        </Note>
      )}
      {!health?.sample_data_enabled && health?.weather === "cached" && (
        <Note tone="grey">{lang === "hi" ? "पहले से सहेजा गया वास्तविक डेटा दिखाया जा रहा है।" : "Showing previously saved real data where available."}</Note>
      )}

      <Link href="/log" aria-label={t("log")}
        className="fixed z-30 bottom-[84px] right-4 sm:right-[calc(50%-264px)] h-14 rounded-full bg-primary text-white shadow-lg px-5 inline-flex items-center gap-2 font-bold">
        <Plus /> {t("log")}
      </Link>
    </div>
  );
}
