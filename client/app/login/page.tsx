"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Card, ErrorBanner } from "@/components/ui";
import { api } from "@/lib/api";
import { useLang } from "@/lib/i18n";

export default function LoginPage() {
  const { lang } = useLang();
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api("/api/auth/login", { method: "POST", json: { password } });
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-sm pt-12">
      <h1 className="text-[26px] font-extrabold">CropTrail</h1>
      <p className="mt-1 text-muted">{lang === "hi" ? "जारी रखने के लिए साइन इन करें।" : "Sign in to continue."}</p>
      <Card className="mt-5">
        <form onSubmit={submit} className="space-y-3">
          <ErrorBanner message={error} onClose={() => setError(null)} />
          <label className="block">
            <span className="block text-[13px] font-semibold text-muted">
              {lang === "hi" ? "पासवर्ड" : "Password"}
            </span>
            <input autoComplete="current-password" type="password" required maxLength={256} value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full min-h-[48px] rounded-xl border border-line bg-white px-3 outline-none" />
          </label>
          <Button type="submit" disabled={busy || !password} className="w-full">
            {busy ? (lang === "hi" ? "जाँच रहे हैं…" : "Signing in…") : (lang === "hi" ? "साइन इन" : "Sign in")}
          </Button>
        </form>
      </Card>
    </div>
  );
}
