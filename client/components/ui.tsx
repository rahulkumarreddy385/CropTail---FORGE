"use client";
import { AlertTriangle, X } from "lucide-react";
import { useState } from "react";

export function Card({ children, className = "", onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) {
  return (
    <div onClick={onClick} className={`bg-white border border-line rounded-card p-4 ${onClick ? "cursor-pointer active:bg-paper" : ""} ${className}`}>
      {children}
    </div>
  );
}

const CHIP = {
  green: "bg-primary-soft text-primary-dark",
  amber: "bg-warn-soft text-[#8A5300]",
  red: "bg-danger-soft text-danger",
  blue: "bg-info-soft text-info",
  grey: "bg-[#EEECE6] text-muted",
};
export function Chip({ tone = "grey", children, className = "" }: { tone?: keyof typeof CHIP; children: React.ReactNode; className?: string }) {
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[13px] font-semibold ${CHIP[tone]} ${className}`}>{children}</span>;
}

export function Button({
  children, onClick, variant = "primary", disabled, className = "", type = "button",
}: {
  children: React.ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "danger" | "ghost";
  disabled?: boolean; className?: string; type?: "button" | "submit";
}) {
  const styles = {
    primary: "bg-primary text-white active:bg-primary-dark",
    secondary: "bg-white border border-line text-ink active:bg-paper",
    danger: "bg-danger text-white",
    ghost: "text-primary",
  }[variant];
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`min-h-[48px] rounded-xl px-4 font-semibold inline-flex items-center justify-center gap-2 disabled:opacity-50 ${styles} ${className}`}>
      {children}
    </button>
  );
}

export function ErrorBanner({ message, onClose }: { message: string | null; onClose?: () => void }) {
  const [hidden, setHidden] = useState(false);
  if (!message || hidden) return null;
  return (
    <div role="alert" className="flex items-start gap-2 rounded-card bg-danger-soft text-danger p-3 text-[15px]">
      <AlertTriangle size={20} className="shrink-0 mt-0.5" />
      <div className="flex-1">{message}</div>
      <button aria-label="Dismiss" onClick={() => { setHidden(true); onClose?.(); }} className="p-1 -m-1"><X size={18} /></button>
    </div>
  );
}

export function Note({ tone = "amber", children }: { tone?: "amber" | "blue" | "grey"; children: React.ReactNode }) {
  const c = { amber: "bg-warn-soft text-[#7A4A00]", blue: "bg-info-soft text-info", grey: "bg-[#EEECE6] text-muted" }[tone];
  return <div className={`rounded-card p-3 text-[15px] ${c}`}>{children}</div>;
}

export function Skeleton({ className = "h-24" }: { className?: string }) {
  return <div className={`animate-pulse rounded-card bg-[#ECE8DD] ${className}`} />;
}

export function SectionTitle({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between mt-6 mb-2">
      <h2 className="text-[15px] font-bold uppercase tracking-wide text-muted">{children}</h2>
      {right}
    </div>
  );
}

export function Field({ label, children, missing }: { label: string; children: React.ReactNode; missing?: boolean }) {
  return (
    <label className={`block rounded-xl px-3 py-2 ${missing ? "bg-warn-soft ring-1 ring-warn" : "bg-paper"}`}>
      <span className="block text-[13px] font-semibold text-muted">{label}</span>
      {children}
    </label>
  );
}

export const inputCls = "w-full bg-transparent text-[17px] py-1 outline-none";

export function ModeChip({ mode, kind }: { mode?: string | null; kind?: string | null }) {
  if (!mode || mode === "live") return null;
  return <Chip tone="grey">{kind === "synthetic" ? "cached · sample data" : "cached"}</Chip>;
}
