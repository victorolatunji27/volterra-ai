// SVG icon set ported from the design prototype (ICONS + svgIcon).
import React from "react";

type PathDef = string | { tag: string; attrs: Record<string, unknown> };

export function svgIcon(paths: PathDef | PathDef[], size = 20) {
  const list = Array.isArray(paths) ? paths : [paths];
  return (
    <svg width={size} height={size} viewBox="0 0 24 24">
      {list.map((d, i) =>
        typeof d === "string" ? (
          <path key={i} d={d} fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" />
        ) : (
          React.createElement(d.tag, { key: i, ...d.attrs })
        )
      )}
    </svg>
  );
}

export const ICONS: Record<string, PathDef[]> = {
  scan: [
    { tag: "circle", attrs: { cx: 12, cy: 12, r: 8.5, fill: "none", stroke: "currentColor", strokeWidth: 1.7 } },
    { tag: "circle", attrs: { cx: 12, cy: 12, r: 3.4, fill: "none", stroke: "currentColor", strokeWidth: 1.7 } },
    { tag: "circle", attrs: { cx: 12, cy: 12, r: 1, fill: "currentColor" } },
  ],
  journal: ["M5 4.5A1.5 1.5 0 016.5 3H18a1 1 0 011 1v15a1 1 0 01-1 1H6.5A1.5 1.5 0 015 18.5v-14z", "M9 7.5h6M9 11h6M9 14.5h3"],
  analytics: ["M4 20V5", "M4 20h16", "M8 20v-6", "M12.5 20V9", "M17 20v-9"],
  alerts: ["M18 8.5a6 6 0 10-12 0c0 6-2.2 7.5-2.2 7.5h16.4S18 14.5 18 8.5z", "M13.7 19a2 2 0 01-3.4 0"],
  settings: [
    { tag: "circle", attrs: { cx: 12, cy: 12, r: 3, fill: "none", stroke: "currentColor", strokeWidth: 1.7 } },
    "M19.4 13.5a1.7 1.7 0 00.3 1.9l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-2.9 1.2V21a2 2 0 11-4 0v-.2a1.7 1.7 0 00-2.9-1.1l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00-1.2-2.9H3a2 2 0 110-4h.2A1.7 1.7 0 004.3 7l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.9.3H9a1.7 1.7 0 001-1.6V3a2 2 0 114 0v.2a1.7 1.7 0 001 1.6 1.7 1.7 0 001.9-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.9V9a1.7 1.7 0 001.6 1H21a2 2 0 110 4h-.2a1.7 1.7 0 00-1.6 1z",
  ],
};

export const playIcon = svgIcon([{ tag: "path", attrs: { d: "M8 5v14l11-7z", fill: "currentColor", stroke: "currentColor", strokeWidth: 1.4, strokeLinejoin: "round" } }], 17);
export const rescanIcon = svgIcon(["M20 12a8 8 0 10-2.3 5.6M20 12v5h-5"], 16);
