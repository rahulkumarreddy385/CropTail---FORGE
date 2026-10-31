"use client";
import { Camera, Droplets, Hammer, Leaf, Mic, NotebookPen, Package, PenLine, Sprout, SprayCan, Tractor, Trash2, Users, Wheat, IndianRupee, Database } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useApp } from "@/components/Shell";
import { Button, Card, Chip, ErrorBanner, inputCls, ModeChip, Note, SectionTitle, Skeleton } from "@/components/ui";
import { api, Entry, Plot, Season } from "@/lib/api";
import { inr, num, shortDate } from "@/lib/format";
import { CATEGORY_LABEL, CROP_LABEL, useLang } from "@/lib/i18n";

const CAT_ICON: Record<string, any> = {
  sowing: Sprout, seed: Leaf, land_prep: Tractor, fertiliser: Package, pesticide: SprayCan, labour: Users,
  irrigation: Droplets, harvest: Wheat, sale: IndianRupee, note: NotebookPen,
};
const SRC_ICON: Record<string, any> = { text: PenLine, voice: Mic, photo: Camera, seed: Database, form: Hammer };

function NdviChart({ series, events }: { series: { date: string; ndvi: number }[]; events: { event_date: string }[] }) {
  if (series.length < 2) return null;
  const W = 340, H = 150, pad = { l: 28, r: 8, t: 10, b: 22 };
  const t0 = new Date(series[0].date).getTime();
  const t1 = new Date(series[series.length - 1].date).getTime();
  const x = (d: string) => pad.l + ((new Date(d).getTime() - t0) / Math.max(1, t1 - t0)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v) * (H - pad.t - pad.b);
  const path = series.map((p, i) => `${i ? "L" : "M"}${x(p.date).toFixed(1)},${y(p.ndvi).toFixed(1)}`).join(" ");
  const ticks = [series[0], series[Math.floor(series.length / 2)], series[series.length - 1]];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="NDVI over time">
      {[0, 0.5, 1].map((v) => (
        <g key={v}>
          <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="#E3DED2" />
          <text x={2} y={y(v) + 4} fontSize="10" fill="#5E665F">{v}</text>
        </g>
      ))}
      {events.filter((e) => new Date(e.event_date).getTime() >= t0 && new Date(e.event_date).getTime() <= t1).map((e) => (
        <line key={e.event_date} x1={x(e.event_date)} x2={x(e.event_date)} y1={pad.t} y2={H - pad.b} stroke="#B3261E" strokeDasharray="4 3" />
      ))}
      <path d={path} fill="none" stroke="#1F7A4D" strokeWidth="2.5" strokeLinejoin="round" />
      {series.map((p) => <circle key={p.date} cx={x(p.date)} cy={y(p.ndvi)} r="3" fill="#1F7A4D" />)}
      {ticks.map((p, i) => (
        <text key={p.date} x={x(p.date)} y={H - 6} fontSize="10" fill="#5E665F" textAnchor={i === 0 ? "start" : i === 2 ? "end" : "middle"}>
          {new Date(p.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
        </text>
      ))}
    </svg>
  );
}

function LedgerInner() {
  const { t, lang } = useLang();
  const { toast } = useApp();
  const params = useSearchParams();
  const [plots, setPlots] = useState<Plot[]>([]);
  const [plotId, setPlotId] = useState<string | null>(params.get("plot"));
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [seasonId, setSeasonId] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [cat, setCat] = useState<string>("");
  const [ndvi, setNdvi] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editVals, setEditVals] = useState<{ item: string; cost: string; qty: string }>({ item: "", cost: "", qty: "" });

  useEffect(() => {
    api<Plot[]>("/api/plots?include_risk=false").then((ps) => {
      setPlots(ps);
      if (!plotId && ps[0]) setPlotId(ps[ps.length > 1 ? 1 : 0].plot_id);
    }).catch((e) => setError(e.message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!plotId) return;
    api<Season[]>(`/api/seasons?plot_id=${plotId}`).then((ss) => {
      setSeasons(ss);
      setSeasonId((ss.find((s) => s.status === "active") || ss[0])?.season_id || null);
    });
    setNdvi(null);
    api(`/api/plots/${plotId}/ndvi`).then(setNdvi).catch(() => setNdvi({ available: false }));
  }, [plotId]);

  const loadSeason = useCallback(() => {
    if (!seasonId) return;
    setEntries(null);
    api(`/api/seasons/${seasonId}/metrics`).then(setMetrics).catch((e) => setError(e.message));
    api<{ entries: Entry[] }>(`/api/entries?season_id=${seasonId}${cat ? `&category=${cat}` : ""}`)
      .then((r) => setEntries(r.entries)).catch((e) => setError(e.message));
  }, [seasonId, cat]);
  useEffect(loadSeason, [loadSeason]);

  const grouped = useMemo(() => {
    const g: Record<string, Entry[]> = {};
    (entries || []).forEach((e) => (g[e.entry_date] = g[e.entry_date] || []).push(e));
    return Object.entries(g);
  }, [entries]);

  const remove = async (id: string) => {
    if (!confirm(lang === "hi" ? "यह एंट्री हटाएँ?" : "Delete this entry?")) return;
    try {
      await api(`/api/entries/${id}`, { method: "DELETE" });
      toast(lang === "hi" ? "हटा दिया" : "Deleted");
      loadSeason();
    } catch (e: any) {
      setError(e.message);
    }
  };
  const saveEdit = async (id: string) => {
    try {
      await api(`/api/entries/${id}`, { method: "PATCH", json: {
        item: editVals.item || null,
        cost_inr: editVals.cost === "" ? null : Number(editVals.cost),
        quantity: editVals.qty === "" ? null : Number(editVals.qty),
      } });
      setEditing(null);
      loadSeason();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const season = seasons.find((s) => s.season_id === seasonId);
  const maxCat = metrics ? Math.max(1, ...Object.values<number>(metrics.cost_by_category)) : 1;
  const profitVal = metrics?.profit ?? metrics?.projected?.projected_profit ?? null;

  return (
    <div className="space-y-3">
      <h1 className="text-[24px] font-extrabold">{t("ledger")}</h1>
      <ErrorBanner message={error} onClose={() => setError(null)} />

      <div className="flex gap-2 overflow-x-auto -mx-4 px-4 pb-1">
        {plots.map((p) => (
          <button key={p.plot_id} onClick={() => setPlotId(p.plot_id)}
            className={`shrink-0 min-h-[44px] rounded-full px-4 border font-semibold ${plotId === p.plot_id ? "bg-primary text-white border-primary" : "bg-white border-line"}`}>
            {p.name}
          </button>
        ))}
      </div>
      {seasons.length > 0 && (
        <select value={seasonId || ""} onChange={(e) => setSeasonId(e.target.value)}
          className="w-full min-h-[48px] rounded-xl border border-line bg-white px-3 font-semibold">
          {seasons.map((s) => (
            <option key={s.season_id} value={s.season_id}>
              {CROP_LABEL[s.crop]?.[lang]} · {s.season_label}{s.status === "active" ? (lang === "hi" ? " (चालू)" : " (active)") : ""}
            </option>
          ))}
        </select>
      )}

      {!metrics ? <Skeleton className="h-28" /> : (
        <div className="grid grid-cols-2 gap-2">
          <Card><p className="text-[13px] text-muted">{t("totalCost")}</p><p className="text-[22px] font-extrabold">{inr(metrics.total_cost)}</p></Card>
          <Card><p className="text-[13px] text-muted">{t("harvest")}</p><p className="text-[22px] font-extrabold">{metrics.harvest_quintals ? `${num(metrics.harvest_quintals)} q` : "-"}</p></Card>
          <Card>
            <p className="text-[13px] text-muted">{t("costPerQ")}</p>
            <p className="text-[22px] font-extrabold">{metrics.cost_per_quintal !== null ? inr(metrics.cost_per_quintal) : "-"}</p>
            {metrics.cost_per_quintal === null && <p className="text-[12px] text-muted">{t("addHarvest")}</p>}
            {metrics.benchmark && (
              <p className="text-[12px] text-muted mt-1">
                {Math.abs(metrics.benchmark.difference_pct)}% {metrics.benchmark.difference_pct >= 0 ? (lang === "hi" ? "राज्य औसत से ज़्यादा" : "above state average") : (lang === "hi" ? "राज्य औसत से कम" : "below state average")}
                {metrics.benchmark.source.includes("placeholder") && <span className="block text-warn">(sample benchmark)</span>}
              </p>
            )}
          </Card>
          <Card>
            <p className="text-[13px] text-muted">{metrics.profit !== null ? t("profit") : t("projectedProfit")}</p>
            <p className={`text-[22px] font-extrabold ${profitVal !== null && profitVal < 0 ? "text-danger" : ""}`}>{inr(profitVal)}</p>
            {metrics.profit === null && metrics.price && (
              <p className="text-[12px] text-muted">@ {inr(metrics.price.modal_price)}/q</p>
            )}
          </Card>
        </div>
      )}

      {metrics && Object.keys(metrics.cost_by_category).length > 0 && (
        <>
          <SectionTitle>{t("costByCategory")}</SectionTitle>
          <Card className="space-y-2.5">
            {Object.entries<number>(metrics.cost_by_category).map(([c, v]) => (
              <div key={c}>
                <div className="flex justify-between text-[15px]"><span>{CATEGORY_LABEL[c]?.[lang] || c}</span><b>{inr(v)}</b></div>
                <div className="h-2.5 rounded-full bg-paper mt-1"><div className="h-2.5 rounded-full bg-primary" style={{ width: `${(v / maxCat) * 100}%` }} /></div>
              </div>
            ))}
          </Card>
        </>
      )}

      {metrics?.price && (
        <Card className="flex items-center justify-between">
          <div>
            <p className="text-[13px] text-muted">{t("mandiPrice")}</p>
            <p className="font-bold">{CROP_LABEL[season?.crop || "other"]?.[lang]} @ {metrics.price.market}: {inr(metrics.price.modal_price)}/q</p>
            <p className="text-[13px] text-muted">{lang === "hi" ? "तारीख" : "as of"} {shortDate(metrics.price.arrival_date, lang)}</p>
          </div>
          <ModeChip mode={metrics.price.mode} kind={metrics.price.source?.includes("placeholder") ? "synthetic" : null} />
        </Card>
      )}

      <SectionTitle right={ndvi?.available && <ModeChip mode={ndvi.mode} kind={ndvi.fixture_kind} />}>{t("cropHealth")}</SectionTitle>
      <Card>
        {!ndvi ? <Skeleton className="h-32" /> : !ndvi.available ? (
          <p className="text-muted">{ndvi.message || "Satellite data not available for this plot."}</p>
        ) : ndvi.series.length < 2 ? (
          <p className="text-muted">{ndvi.message || "No clear satellite image for this period (clouds)."}</p>
        ) : (
          <>
            <NdviChart series={ndvi.series} events={ndvi.events || []} />
            <p className="text-[12px] text-muted mt-1">
              {lang === "hi" ? "हरी रेखा = फसल की हरियाली (0-1)। लाल = नुकसान की तारीख। बादल वाले चित्र हटाए गए।" : "Green = crop greenness (0-1). Red dashes = loss events. Cloudy images removed."}
            </p>
          </>
        )}
      </Card>

      <SectionTitle right={
        <select value={cat} onChange={(e) => setCat(e.target.value)} className="rounded-lg border border-line bg-white px-2 py-1 text-[14px]">
          <option value="">{lang === "hi" ? "सभी" : "All"}</option>
          {Object.keys(CATEGORY_LABEL).map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c][lang]}</option>)}
        </select>
      }>{t("timeline")}</SectionTitle>

      {entries === null && <Skeleton />}
      {entries?.length === 0 && <Note tone="grey">{t("nothingLogged")}</Note>}
      {grouped.map(([d, list]) => (
        <div key={d}>
          <p className="text-[13px] font-bold text-muted mb-1">{shortDate(d, lang)}</p>
          <Card className="divide-y divide-line p-0">
            {list.map((e) => {
              const Icon = CAT_ICON[e.category] || NotebookPen;
              const Src = SRC_ICON[e.source] || PenLine;
              return (
                <div key={e.entry_id} className="p-3">
                  <button className="w-full flex items-center gap-3 text-left" onClick={() => {
                    setEditing(editing === e.entry_id ? null : e.entry_id);
                    setEditVals({ item: e.item || "", cost: e.cost_inr?.toString() || "", qty: e.quantity?.toString() || "" });
                  }}>
                    <span className="h-10 w-10 shrink-0 rounded-xl bg-primary-soft text-primary grid place-items-center"><Icon size={20} /></span>
                    <span className="flex-1 min-w-0">
                      <span className="block font-semibold truncate">{e.item || CATEGORY_LABEL[e.category]?.[lang]}</span>
                      <span className="block text-[13px] text-muted">
                        {CATEGORY_LABEL[e.category]?.[lang]}{e.quantity !== null ? ` · ${num(e.quantity)} ${e.unit !== "none" ? e.unit : ""}` : ""}
                      </span>
                    </span>
                    <span className="text-right">
                      <span className="block font-bold">{e.cost_inr !== null ? inr(e.cost_inr) : ""}</span>
                      <Src size={14} className="inline text-muted" aria-label={e.source} />
                    </span>
                  </button>
                  {editing === e.entry_id && (
                    <div className="mt-3 space-y-2">
                      <div className="grid grid-cols-3 gap-2">
                        <input className={`${inputCls} bg-paper rounded-lg px-2 col-span-3`} placeholder={t("item")} value={editVals.item} onChange={(ev) => setEditVals({ ...editVals, item: ev.target.value })} />
                        <input className={`${inputCls} bg-paper rounded-lg px-2`} inputMode="decimal" placeholder={t("quantity")} value={editVals.qty} onChange={(ev) => setEditVals({ ...editVals, qty: ev.target.value })} />
                        <input className={`${inputCls} bg-paper rounded-lg px-2 col-span-2`} inputMode="decimal" placeholder={t("cost")} value={editVals.cost} onChange={(ev) => setEditVals({ ...editVals, cost: ev.target.value })} />
                      </div>
                      <div className="flex gap-2">
                        <Button className="flex-1" onClick={() => saveEdit(e.entry_id)}>{t("save")}</Button>
                        <Button variant="secondary" onClick={() => remove(e.entry_id)} className="text-danger"><Trash2 size={18} /></Button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </Card>
        </div>
      ))}
      {season && <p className="text-center text-[12px] text-muted pt-2"><Chip>{season.season_label}</Chip></p>}
    </div>
  );
}

export default function LedgerPage() {
  return (
    <Suspense fallback={<Skeleton className="h-40" />}>
      <LedgerInner />
    </Suspense>
  );
}
