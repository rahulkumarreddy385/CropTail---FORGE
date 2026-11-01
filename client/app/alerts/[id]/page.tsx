"use client";
import { Camera, FileText, Loader2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { EVENT_ICON } from "@/components/eventIcons";
import { useApp } from "@/components/Shell";
import { Button, Card, Chip, ErrorBanner, Field, inputCls, ModeChip, Note, SectionTitle, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { countdown, shortDate } from "@/lib/format";
import { EVENT_LABEL, useLang } from "@/lib/i18n";

export default function EventPage() {
  const { id } = useParams<{ id: string }>();
  const { t, lang } = useLang();
  const { refreshBadges, toast } = useApp();
  const router = useRouter();
  const [ev, setEv] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loss, setLoss] = useState("");
  const [notes, setNotes] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api(`/api/events/${id}`).then((e: any) => {
      setEv(e);
      setLoss(e.estimated_loss_quintals?.toString() || "");
      setNotes(e.farmer_notes || "");
    }).catch((e) => setError(e.message));
  }, [id]);
  useEffect(load, [load]);

  const act = async (action: "confirm" | "dismiss") => {
    setBusy(true);
    try {
      await api(`/api/events/${id}`, { method: "PATCH", json: { action } });
      refreshBadges();
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const saveDetails = async () => {
    try {
      await api(`/api/events/${id}`, { method: "PATCH", json: {
        estimated_loss_quintals: loss === "" ? null : Number(loss), farmer_notes: notes || null } });
      toast(lang === "hi" ? "सेव हुआ" : "Saved");
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };
  const addPhoto = async (file: File) => {
    if (file.size > 8 * 1024 * 1024) return setError("Please use a photo smaller than 8 MB.");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("event_id", id);
    setBusy(true);
    try {
      await api("/api/photos", { method: "POST", body: fd });
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      if (ev.status === "confirmed") await saveDetails();
      const out = await api<{ file_url: string }>(`/api/events/${id}/evidence-pack`, { method: "POST" });
      toast(lang === "hi" ? "सबूत PDF तैयार" : "Evidence pack ready");
      window.open(out.file_url, "_blank");
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!ev) return <div className="space-y-3"><ErrorBanner message={error} /><Skeleton className="h-40" /><Skeleton /></div>;
  const Icon = EVENT_ICON[ev.type];
  const maxRain = Math.max(1, ...(ev.weather?.days || []).map((d: any) => d.precipitation_sum || 0));

  return (
    <div className="space-y-3">
      <button onClick={() => router.push("/alerts")} className="text-primary font-semibold">← {t("alerts")}</button>
      <div className="flex gap-3 items-center">
        <span className="h-12 w-12 rounded-xl bg-info-soft text-info grid place-items-center"><Icon /></span>
        <div>
          <h1 className="text-[22px] font-extrabold leading-tight">{EVENT_LABEL[ev.type]?.[lang]}</h1>
          <p className="text-muted">{ev.plot_name} · {shortDate(ev.event_date, lang)}</p>
        </div>
      </div>
      <ErrorBanner key={error || ""} message={error} onClose={() => setError(null)} />
      {ev.is_demo && (
        <Note tone="amber">
          {lang === "hi"
            ? "यह काल्पनिक डेमो घटना है। फोटो प्लेसहोल्डर हैं; इस रिकॉर्ड को असली नुकसान या बीमा दावे के लिए इस्तेमाल न करें।"
            : "Fictional demo event. Photos are placeholders; do not use this record as real loss or insurance-claim evidence."}
        </Note>
      )}
      <Card>
        <p>{ev.trigger_detail}</p>
        <div className="mt-2 flex gap-2 flex-wrap">
          <Chip tone={ev.status === "suspected" ? "amber" : ev.status === "confirmed" ? "blue" : "grey"}>{ev.status}</Chip>
          {ev.status === "confirmed" && !ev.past_deadline && <Chip tone="blue">{t("reportWithin")} {countdown(ev.seconds_left)}</Chip>}
        </div>
        {ev.status === "confirmed" && ev.past_deadline && <div className="mt-3"><Note>{t("windowPassed")}</Note></div>}
        {ev.status === "suspected" && (
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Button disabled={busy} onClick={() => act("confirm")}>{t("yesDamaged")}</Button>
            <Button variant="secondary" disabled={busy} onClick={() => act("dismiss")}>{t("no")}</Button>
          </div>
        )}
      </Card>

      <SectionTitle right={<ModeChip mode={ev.weather?.mode} kind={ev.weather?.fixture_kind} />}>
        {lang === "hi" ? "क्षेत्र का मौसम" : "Area weather"}
      </SectionTitle>
      <Card>
        {ev.weather?.error ? <p className="text-danger">{ev.weather.error}</p> : (
          <div className="flex items-end gap-1.5 h-32">
            {ev.weather.days.map((d: any) => (
              <div key={d.date} className="flex-1 flex flex-col items-center justify-end h-full">
                <span className="text-[11px] font-semibold">{d.precipitation_sum ?? "n/a"}</span>
                <div className={`w-full rounded-t ${d.date === ev.event_date ? "bg-danger" : "bg-primary"} ${d.simulated ? "opacity-60 bg-[repeating-linear-gradient(45deg,#B3261E,#B3261E_4px,#f2b8b5_4px,#f2b8b5_8px)]" : ""}`}
                  style={{ height: `${((d.precipitation_sum || 0) / maxRain) * 80}%`, minHeight: 2 }} />
                <span className="text-[11px] text-muted mt-1">{shortDate(d.date, lang)}</span>
              </div>
            ))}
          </div>
        )}
        <p className="text-[12px] text-muted mt-2">{lang === "hi" ? "मिमी बारिश प्रति दिन (मॉडल ग्रिड डेटा, कुछ किमी)" : "mm rain per day (gridded model data, several km)"}</p>
      </Card>

      <SectionTitle right={ev.ndvi?.available && <ModeChip mode={ev.ndvi.mode} kind={ev.ndvi.fixture_kind} />}>{t("cropHealth")}</SectionTitle>
      <Card>
        {!ev.ndvi?.available ? <p className="text-muted">{ev.ndvi?.message}</p> : (
          <>
            <div className="grid grid-cols-3 text-center">
              <div><p className="text-[12px] text-muted">{lang === "hi" ? "पहले" : "Before"}</p><p className="text-[22px] font-extrabold">{ev.ndvi.ndvi_before ?? "-"}</p><p className="text-[12px] text-muted">{shortDate(ev.ndvi.before_date, lang)}</p></div>
              <div><p className="text-[12px] text-muted">{lang === "hi" ? "बाद में" : "After"}</p><p className="text-[22px] font-extrabold">{ev.ndvi.ndvi_after ?? "-"}</p><p className="text-[12px] text-muted">{shortDate(ev.ndvi.after_date, lang)}</p></div>
              <div><p className="text-[12px] text-muted">{lang === "hi" ? "बदलाव" : "Change"}</p><p className={`text-[22px] font-extrabold ${ev.ndvi.ndvi_change_pct < 0 ? "text-danger" : ""}`}>{ev.ndvi.ndvi_change_pct !== null ? `${ev.ndvi.ndvi_change_pct}%` : "-"}</p></div>
            </div>
            {ev.ndvi.notes.map((n: string) => <p key={n} className="text-[13px] text-muted mt-2">{n}</p>)}
          </>
        )}
      </Card>

      <SectionTitle right={ev.status !== "dismissed" && (
        <button onClick={() => fileRef.current?.click()} className="text-primary font-semibold inline-flex items-center gap-1 text-[14px]"><Camera size={16} />{t("addPhoto")}</button>
      )}>{lang === "hi" ? "फोटो" : "Photos"}</SectionTitle>
      <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/heic" capture="environment" hidden
        onChange={(e) => e.target.files?.[0] && addPhoto(e.target.files[0])} />
      {ev.photos.length === 0 ? <Note tone="grey">{lang === "hi" ? "अभी कोई फोटो नहीं।" : "No photos yet."}</Note> : (
        <div className="grid grid-cols-3 gap-2">
          {ev.photos.map((p: any) => (
            <div key={p.photo_id}>
              <img src={p.file_url} alt="" className="aspect-square w-full rounded-xl object-cover" />
              <p className="text-[11px] text-muted mt-0.5">{shortDate(p.taken_at, lang)}{p.vision_tag ? ` · hint: ${p.vision_tag.replace("_", " ")}` : ""}</p>
            </div>
          ))}
        </div>
      )}

      {ev.status !== "dismissed" && (
        <>
          <SectionTitle>{lang === "hi" ? "आपका अनुमान" : "Your estimate"}</SectionTitle>
          <Card className="space-y-2">
            <Field label={t("lossEstimate")}><input inputMode="decimal" className={inputCls} value={loss} onChange={(e) => setLoss(e.target.value)} /></Field>
            <Field label={t("notes")}><textarea rows={2} maxLength={500} className={inputCls} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
            <Button variant="secondary" className="w-full" onClick={saveDetails}>{t("save")}</Button>
          </Card>
        </>
      )}

      {ev.status === "confirmed" && (
        <Button className="w-full" disabled={busy} onClick={generate}>
          {busy ? <Loader2 className="animate-spin" /> : <FileText />}{t("createPack")}
        </Button>
      )}
      {ev.packs.length > 0 && (
        <Card className="divide-y divide-line p-0">
          {ev.packs.map((p: any) => (
            <a key={p.pack_id} href={p.file_url} target="_blank" className="flex items-center justify-between p-3">
              <span className="inline-flex items-center gap-2"><FileText size={18} className="text-primary" />{p.pack_id}</span>
              <span className="text-[13px] text-muted">{new Date(p.generated_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</span>
            </a>
          ))}
        </Card>
      )}
      <p className="text-[12px] text-muted">
        {lang === "hi" ? "CropTrail केवल रिकॉर्ड बनाता है। क्लेम आपको खुद आधिकारिक तरीके से जमा करना होगा।"
          : "CropTrail only prepares the record. You submit any claim yourself through the official channel."}
      </p>
    </div>
  );
}
