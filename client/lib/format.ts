export function inr(value: number | null | undefined, decimals = false): string {
  if (value === null || value === undefined) return "-";
  return (
    "₹" +
    value.toLocaleString("en-IN", {
      minimumFractionDigits: decimals ? 2 : 0,
      maximumFractionDigits: decimals ? 2 : 0,
    })
  );
}

export function shortDate(iso: string | null | undefined, lang: "hi" | "en" = "en"): string {
  if (!iso) return "-";
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  return d.toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", { day: "numeric", month: "short" });
}

export function longDate(iso: string, lang: "hi" | "en" = "en"): string {
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  return d.toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
}

export function countdown(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h} h ${m} m`;
}

export function daysBetween(fromIso: string, toIso: string): number {
  return Math.round((new Date(toIso + "T00:00:00").getTime() - new Date(fromIso + "T00:00:00").getTime()) / 86400000);
}

export function num(v: number | null | undefined): string {
  if (v === null || v === undefined) return "";
  return Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100);
}

// Hindi rendering of server-generated weather text (server keeps one canonical English string).
export function alertText(e: { alert_message: string | null; trigger_detail: string; plot_name: string; event_date: string }, lang: "hi" | "en"): string {
  const en = e.alert_message || e.trigger_detail;
  if (lang === "en") return en;
  const mm = en.match(/([\d.]+) mm/);
  const sim = /simulated/i.test(en) ? "[सिमुलेशन] " : "";
  const when = shortDate(e.event_date, "hi");
  if (/hail/i.test(en)) return `${sim}${e.plot_name} के पास ${when} को ओलावृष्टि दर्ज हुई। क्या फसल को नुकसान हुआ? पुष्टि करें और फोटो जोड़ें।`;
  if (mm) return `${sim}${e.plot_name} के पास ${when} को भारी बारिश (${mm[1]} मिमी) दर्ज हुई। क्या फसल को नुकसान हुआ? पुष्टि करें और फोटो जोड़ें।`;
  return en;
}

export function driverText(d: string, lang: "hi" | "en"): string {
  if (lang === "en") return d;
  let m;
  if ((m = d.match(/^Heavy rain ([\d.]+) mm forecast on (\S+)/))) return `${shortDate(m[2], "hi")} को ${m[1]} मिमी भारी बारिश का अनुमान`;
  if ((m = d.match(/^Moderate rain ([\d.]+) mm forecast on (\S+)/))) return `${shortDate(m[2], "hi")} को ${m[1]} मिमी बारिश का अनुमान`;
  if ((m = d.match(/^Heat ([\d.]+) °C forecast on (\S+)/))) return `${shortDate(m[2], "hi")} को ${m[1]} °C गर्मी का अनुमान`;
  if ((m = d.match(/^Wind gusts ([\d.]+) km\/h on (\S+)/))) return `${shortDate(m[2], "hi")} को ${m[1]} किमी/घंटा तेज़ हवा`;
  if ((m = d.match(/^Thunderstorm with hail possible on (\S+)/))) return `${shortDate(m[1], "hi")} को ओले गिरने की संभावना`;
  return d;
}
