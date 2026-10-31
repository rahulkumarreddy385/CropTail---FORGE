"use client";
import { Camera, Check, Loader2, Mic, MicOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useApp } from "@/components/Shell";
import { Button, Card, Chip, ErrorBanner, Field, inputCls, Note, SectionTitle } from "@/components/ui";
import { api, ApiError, ParsedEntry, Plot } from "@/lib/api";
import { CATEGORY_LABEL, useLang } from "@/lib/i18n";

const CATEGORIES = Object.keys(CATEGORY_LABEL);
const UNITS = ["kg", "bag", "quintal", "litre", "hour", "day", "acre", "none"];

export default function LogPage() {
  const { t, lang } = useLang();
  const { toast } = useApp();
  const [text, setText] = useState("");
  const [plots, setPlots] = useState<Plot[]>([]);
  const [draft, setDraft] = useState<ParsedEntry | null>(null);
  const [plotId, setPlotId] = useState<string | null>(null);
  const [source, setSource] = useState<"text" | "voice">("text");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dupId, setDupId] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const [speechOk, setSpeechOk] = useState(true);
  const [photo, setPhoto] = useState<any>(null);
  const recRef = useRef<any>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api<Plot[]>("/api/plots?include_risk=false").then(setPlots).catch(() => {});
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    setSpeechOk(!!SR);
  }, []);

  const toggleMic = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return setSpeechOk(false);
    if (listening) {
      recRef.current?.stop();
      return;
    }
    const rec = new SR();
    rec.lang = lang === "hi" ? "hi-IN" : "en-IN";
    rec.interimResults = false;
    rec.onresult = (e: any) => {
      const said = Array.from(e.results).map((r: any) => r[0].transcript).join(" ");
      setText((prev) => (prev ? prev + " " : "") + said);
      setSource("voice");
    };
    rec.onerror = () => {
      setListening(false);
      setSpeechOk(false);
    };
    rec.onend = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    rec.start();
  };

  const parse = async () => {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const out = await api<any>("/api/entries/parse", { method: "POST", json: { text } });
      setDraft(out.draft);
      setPlotId(out.resolved_plot_id);
      setNotice(out.notice);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const save = async (force = false) => {
    if (!draft) return;
    if (!plotId) return setError(t("whichPlot"));
    setBusy(true);
    setError(null);
    try {
      const saved = await api<any>("/api/entries", {
        method: "POST",
        json: {
          plot_id: plotId, entry_date: draft.entry_date, category: draft.category, item: draft.item || null,
          quantity: draft.quantity, unit: draft.unit, cost_inr: draft.cost_inr, raw_text: text || null,
          photo_id: photo?.photo_id || null, source: photo && !text ? "photo" : source, force,
        },
      });
      toast(`${t("savedTo")} ${saved.plot_name}`);
      setDraft(null);
      setText("");
      setPhoto(null);
      setDupId(null);
      setSource("text");
    } catch (e: any) {
      if (e instanceof ApiError && e.status === 409) setDupId(e.detail?.entry_id || "dup");
      else setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const onPhoto = async (file: File) => {
    setError(null);
    if (file.size > 8 * 1024 * 1024) return setError("Please use a photo smaller than 8 MB.");
    const pid = plotId || plots[0]?.plot_id;
    const fd = new FormData();
    fd.append("file", file);
    if (pid) fd.append("plot_id", pid);
    setBusy(true);
    try {
      const ph = await api<any>("/api/photos", { method: "POST", body: fd });
      setPhoto(ph);
      if (!draft) {
        setDraft({ entry_date: ph.taken_at.slice(0, 10), category: "note", item: "photo", quantity: null, unit: null,
          cost_inr: null, plot_hint: null, confidence: 1, missing_fields: [] });
        setPlotId(pid || null);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const set = (k: keyof ParsedEntry, v: any) => setDraft((d) => (d ? { ...d, [k]: v } : d));
  const miss = (k: string) => !!draft?.missing_fields.includes(k) && (draft as any)[k] == null;

  return (
    <div className="space-y-3">
      <h1 className="text-[24px] font-extrabold">{t("log")}</h1>
      <Card>
        <textarea value={text} onChange={(e) => { setText(e.target.value); setSource("text"); }} maxLength={500} rows={4}
          placeholder={t("logPlaceholder")} className="w-full resize-none bg-paper rounded-xl p-3 outline-none text-[18px]" />
        <div className="mt-3 flex gap-2">
          <button onClick={toggleMic} disabled={!speechOk} title={!speechOk ? t("voiceUnavailable") : undefined}
            aria-label="Voice input"
            className={`h-12 w-12 rounded-xl grid place-items-center border ${listening ? "bg-danger text-white border-danger" : "bg-white border-line"} disabled:opacity-40`}>
            {speechOk ? <Mic /> : <MicOff />}
          </button>
          <button onClick={() => fileRef.current?.click()} aria-label="Add photo"
            className="h-12 w-12 rounded-xl grid place-items-center border border-line bg-white"><Camera /></button>
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/heic" capture="environment" hidden
            onChange={(e) => e.target.files?.[0] && onPhoto(e.target.files[0])} />
          <Button className="flex-1" onClick={parse} disabled={busy || !text.trim()}>
            {busy ? <Loader2 className="animate-spin" /> : t("parse")}
          </Button>
        </div>
        {listening && <p className="mt-2 text-danger font-semibold">{t("listening")}</p>}
        {!speechOk && <p className="mt-2 text-[14px] text-muted">{t("voiceUnavailable")}</p>}
        {photo && (
          <div className="mt-3 flex gap-3 items-center">
            <img src={photo.file_url} alt="" className="h-16 w-16 rounded-lg object-cover" />
            <div className="text-[14px]">
              {photo.vision_tag && <Chip tone="blue">AI hint: {photo.vision_tag.replace("_", " ")}</Chip>}
              <p className="text-muted mt-1">{photo.location_source === "exif" ? "GPS from photo" : "Location: plot pin"}</p>
            </div>
          </div>
        )}
      </Card>

      <ErrorBanner key={error || ""} message={error} onClose={() => setError(null)} />
      {notice && <Note>{notice}</Note>}

      {draft && (
        <Card className="border-primary">
          <SectionTitle>{lang === "hi" ? "जाँचें और पक्का करें" : "Check and confirm"}</SectionTitle>
          {draft.missing_fields.length > 0 && <p className="mb-2 text-[14px] text-[#7A4A00]">{t("checkFields")}</p>}
          <div className="space-y-2">
            <Field label={t("plot")} missing={!plotId}>
              <div className="flex flex-wrap gap-2 pt-1">
                {plots.map((p) => (
                  <button key={p.plot_id} onClick={() => setPlotId(p.plot_id)}
                    className={`min-h-[44px] rounded-xl px-3 border font-semibold ${plotId === p.plot_id ? "bg-primary text-white border-primary" : "bg-white border-line"}`}>
                    {p.name}
                  </button>
                ))}
              </div>
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label={t("date")} missing={miss("entry_date")}>
                <input type="date" className={inputCls} value={draft.entry_date || ""} onChange={(e) => set("entry_date", e.target.value)} />
              </Field>
              <Field label={t("category")} missing={miss("category")}>
                <select className={inputCls} value={draft.category || "note"} onChange={(e) => set("category", e.target.value)}>
                  {CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c][lang]}</option>)}
                </select>
              </Field>
            </div>
            <Field label={t("item")}>
              <input className={inputCls} value={draft.item || ""} maxLength={80} onChange={(e) => set("item", e.target.value || null)} />
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label={t("quantity")} missing={miss("quantity")}>
                <div className="flex gap-1">
                  <input inputMode="decimal" className={inputCls} value={draft.quantity ?? ""}
                    onChange={(e) => set("quantity", e.target.value === "" ? null : Number(e.target.value))} />
                  <select className="bg-transparent" value={draft.unit || "none"} onChange={(e) => set("unit", e.target.value)}>
                    {UNITS.map((u) => <option key={u}>{u}</option>)}
                  </select>
                </div>
              </Field>
              <Field label={t("cost")} missing={miss("cost_inr")}>
                <input inputMode="decimal" className={inputCls} value={draft.cost_inr ?? ""}
                  onChange={(e) => set("cost_inr", e.target.value === "" ? null : Number(e.target.value))} />
              </Field>
            </div>
          </div>
          {dupId ? (
            <div className="mt-3 space-y-2">
              <Note>{t("duplicate")}</Note>
              <div className="grid grid-cols-2 gap-2">
                <Button onClick={() => save(true)} disabled={busy}>{t("saveAnyway")}</Button>
                <Button variant="secondary" onClick={() => { setDupId(null); setDraft(null); }}>{t("cancel")}</Button>
              </div>
            </div>
          ) : (
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Button onClick={() => save(false)} disabled={busy}><Check size={20} />{t("confirm")}</Button>
              <Button variant="secondary" onClick={() => { setDraft(null); setPhoto(null); }}>{t("cancel")}</Button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
