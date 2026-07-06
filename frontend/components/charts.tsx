"use client";
// Pure-SVG chart primitives ported from the design prototype: spark, area, donut.
import React, { useId } from "react";

export function Spark({ data, color, w = 86, h = 28, fill = true }: { data: number[]; color: string; w?: number; h?: number; fill?: boolean }) {
  const id = useId().replace(/[:]/g, "s");
  const mn = Math.min(...data), mx = Math.max(...data), rg = mx - mn || 1;
  const pts = data.map((v, i) => [+((i / (data.length - 1)) * w).toFixed(1), +(h - 2 - ((v - mn) / rg) * (h - 5)).toFixed(1)]);
  const d = "M" + pts.map((p) => p.join(" ")).join(" L");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: "block", overflow: "visible" }}>
      {fill ? (
        <defs>
          <linearGradient id={id} x1={0} y1={0} x2={0} y2={1}>
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
      ) : null}
      {fill ? <path d={`${d} L ${w} ${h} L 0 ${h} Z`} fill={`url(#${id})`} /> : null}
      <path d={d} fill="none" stroke={color} strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Area({ data, color, w, h }: { data: number[]; color: string; w: number; h: number }) {
  const id = useId().replace(/[:]/g, "a");
  const mn = Math.min(...data), mx = Math.max(...data), rg = mx - mn || 1, pad = 10;
  const pts = data.map((v, i) => [+((i / (data.length - 1)) * w).toFixed(1), +(h - pad - ((v - mn) / rg) * (h - pad * 2)).toFixed(1)]);
  const d = "M" + pts.map((p) => p.join(" ")).join(" L");
  const last = pts[pts.length - 1];
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ display: "block", overflow: "visible" }}>
      <defs>
        <linearGradient id={id} x1={0} y1={0} x2={0} y2={1}>
          <stop offset="0%" stopColor={color} stopOpacity={0.26} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
        <linearGradient id={id + "l"} x1={0} y1={0} x2={1} y2={0}>
          <stop offset="0%" stopColor={color} stopOpacity={0.6} />
          <stop offset="100%" stopColor={color} stopOpacity={1} />
        </linearGradient>
      </defs>
      <path d={`${d} L ${w} ${h} L 0 ${h} Z`} fill={`url(#${id})`} />
      <path d={d} fill="none" stroke={`url(#${id}l)`} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r={3.6} fill={color} />
    </svg>
  );
}

export function Donut({ segs, size = 168, sw = 20 }: { segs: { value: number; color: string }[]; size?: number; sw?: number }) {
  const r = (size - sw) / 2, c = size / 2, circ = 2 * Math.PI * r;
  const total = segs.reduce((s, x) => s + x.value, 0);
  let acc = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={c} cy={c} r={r} fill="none" stroke="var(--border)" strokeWidth={sw} />
      <g transform={`rotate(-90 ${c} ${c})`}>
        {segs.map((s, i) => {
          const frac = s.value / total, dash = frac * circ, off = -acc * circ;
          acc += frac;
          return <circle key={i} cx={c} cy={c} r={r} fill="none" stroke={s.color} strokeWidth={sw} strokeDasharray={`${dash} ${circ - dash}`} strokeDashoffset={off} strokeLinecap="butt" style={{ transition: "stroke-dasharray .6s ease" }} />;
        })}
      </g>
    </svg>
  );
}
