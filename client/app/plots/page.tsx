"use client";
import { Crosshair, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useApp } from "@/components/Shell";
import { Button, Card, Chip, ErrorBanner, Field, inputCls, SectionTitle, Skeleton } from "@/components/ui";
import { api, ApiError, Plot } from "@/lib/api";
import { CROP_LABEL, useLang } from "@/lib/i18n";

const EMPTY_PLOT = { name: "", area_acres: "", lat: "", lon: "", survey_number: "", nearest_market: "" };

export default function PlotsPage() {
  const { t, lang } = useLang();
  const { toast } = useApp();
  const [plots, setPlots] = useState<Plot[] | null>(null);
  const [form, setForm] = useState<typeof EMPTY_PLOT | null>(null);
  const [fieldErr, setFieldErr] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [seasonFor, setSeasonFor] = useState<string | null>(null);
  const [season, setSeason] = useState({ crop: "wheat", season_label: "", sowing_date: "", policy_number: "" });
  const [demoBusy, setDemoBusy] = useState(false);

  const load = useCallback(() => {
    api<Plot[]>("/api/plots?include_risk=false").then(setPlots).catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const locate = () => {
    if (!navigator.geolocation || !form) return setError(lang === "hi" ? "लोकेशन उपलब्ध नहीं" : "Location not available");
    navigator.geolocation.getCurrentPosition(
      (pos) => setForm((f) => f && { ...f, lat: pos.coords.latitude.toFixed(5), lon: pos.coords.longitude.toFixed(5) }),
      () => setError(lang === "hi" ? "लोकेशन नहीं मिली" : "Could not get location"),
    );
  };

  const savePlot = async () => {
    if (!form) return;
    setFieldErr({});
    setError(null);
    try {
      await api("/api/plots", { method: "POST", json: {
        name: form.name, area_acres: Number(form.area_acres), lat: Number(form.lat), lon: Number(form.lon),
        survey_number: form.survey_number || null, nearest_market: form.nearest_market || null } });
      setForm(null);
      toast(lang === "hi" ? "खेत जुड़ गया" : "Plot added");
      load();
    } catch (e: any) {
      if (e instanceof ApiError && e.detail?.fields) setFieldErr(e.detail.fields);
      setError(e.message);
    }
  };

  const saveSeason = async () => {
    setError(null);
    try {
      await api("/api/seasons", { method: "POST", json: { plot_id: seasonFor, ...season, policy_number: season.policy_number || null } });
      setSeasonFor(null);
      toast(lang === "hi" ? "नया सीज़न शुरू" : "Season started");
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const resetDemo = async () => {
    if (!confirm(lang === "hi" ? "सारा डेटा डेमो डेटा से बदलें?" : "Replace all data with the demo seed?")) return;
    setDemoBusy(true);
    try {
      await api("/api/demo/reset", { method: "POST" });
      toast(lang === "hi" ? "डेमो डेटा लोड हुआ" : "Demo data restored");
      load();
    } finally {
      setDemoBusy(false);
    }
  };

  const F = (k: keyof typeof EMPTY_PLOT, label: string, mode: "text" | "decimal" = "text") => (
    <div>
      <Field label={label} missing={!!fieldErr[k]}>
        <input inputMode={mode} className={inputCls} value={form![k]} onChange={(e) => setForm({ ...form!, [k]: e.target.value })} />
      </Field>
      {fieldErr[k] && <p className="text-danger text-[13px] mt-0.5">{fieldErr[k]}</p>}
    </div>
  );

  return (
    <div className="space-y-3">
      <h1 className="text-[24px] font-extrabold">{t("managePlots")}</h1>
      <ErrorBanner key={error || ""} message={error} onClose={() => setError(null)} />
      {plots === null && <Skeleton />}
      {plots?.map((p) => (
        <Card key={p.plot_id}>
          <div className="flex justify-between items-start">
            <div>
              <p className="font-bold text-[18px]">{p.name}</p>
              <p className="text-[14px] text-muted">{p.area_acres} {lang === "hi" ? "एकड़" : "acres"} · {p.lat.toFixed(4)}, {p.lon.toFixed(4)}</p>
            </div>
            {p.active_season && <Chip tone="green">{CROP_LABEL[p.active_season.crop]?.[lang]} · {p.active_season.season_label}</Chip>}
          </div>
          {seasonFor === p.plot_id ? (
            <div className="mt-3 space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <Field label={lang === "hi" ? "फसल" : "Crop"}>
                  <select className={inputCls} value={season.crop} onChange={(e) => setSeason({ ...season, crop: e.target.value })}>
                    {Object.keys(CROP_LABEL).map((c) => <option key={c} value={c}>{CROP_LABEL[c][lang]}</option>)}
                  </select>
                </Field>
                <Field label={lang === "hi" ? "बुवाई की तारीख" : "Sowing date"}>
                  <input type="date" className={inputCls} value={season.sowing_date} onChange={(e) => setSeason({ ...season, sowing_date: e.target.value })} />
                </Field>
              </div>
              <Field label={lang === "hi" ? "सीज़न का नाम" : "Season label"}>
                <input className={inputCls} placeholder="Rabi 2026-27" value={season.season_label} onChange={(e) => setSeason({ ...season, season_label: e.target.value })} />
              </Field>
              <Field label={lang === "hi" ? "बीमा आवेदन संख्या (वैकल्पिक)" : "Insurance application no. (optional)"}>
                <input className={inputCls} value={season.policy_number} onChange={(e) => setSeason({ ...season, policy_number: e.target.value })} />
              </Field>
              <p className="text-[13px] text-muted">{lang === "hi" ? "पुराना चालू सीज़न बंद हो जाएगा।" : "The current active season will be closed."}</p>
              <div className="grid grid-cols-2 gap-2">
                <Button onClick={saveSeason}>{t("save")}</Button>
                <Button variant="secondary" onClick={() => setSeasonFor(null)}>{t("cancel")}</Button>
              </div>
            </div>
          ) : (
            <Button variant="ghost" className="mt-1 -ml-4" onClick={() => setSeasonFor(p.plot_id)}><Plus size={18} />{lang === "hi" ? "नया सीज़न" : "New season"}</Button>
          )}
        </Card>
      ))}

      {form ? (
        <Card className="space-y-2">
          {F("name", lang === "hi" ? "खेत का नाम" : "Plot name")}
          {F("area_acres", lang === "hi" ? "रकबा (एकड़)" : "Area (acres)", "decimal")}
          <div className="grid grid-cols-2 gap-2">{F("lat", "Latitude", "decimal")}{F("lon", "Longitude", "decimal")}</div>
          <Button variant="secondary" className="w-full" onClick={locate}><Crosshair size={18} />{lang === "hi" ? "मेरी लोकेशन लें" : "Use my location"}</Button>
          {F("survey_number", lang === "hi" ? "खसरा नंबर (वैकल्पिक)" : "Survey number (optional)")}
          {F("nearest_market", lang === "hi" ? "नज़दीकी मंडी" : "Nearest mandi")}
          <div className="grid grid-cols-2 gap-2">
            <Button onClick={savePlot}>{t("save")}</Button>
            <Button variant="secondary" onClick={() => { setForm(null); setFieldErr({}); }}>{t("cancel")}</Button>
          </div>
        </Card>
      ) : (
        <Button className="w-full" onClick={() => setForm({ ...EMPTY_PLOT })}><Plus />{lang === "hi" ? "खेत जोड़ें" : "Add plot"}</Button>
      )}

      <SectionTitle>{lang === "hi" ? "डेमो" : "Demo"}</SectionTitle>
      <Button variant="secondary" className="w-full" disabled={demoBusy} onClick={resetDemo}>
        {lang === "hi" ? "डेमो डेटा फिर से लोड करें" : "Reset to demo data"}
      </Button>
    </div>
  );
}
