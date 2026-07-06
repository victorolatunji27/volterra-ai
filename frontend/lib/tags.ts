// Strategy tag → color/label map, ported from the design prototype.
import { WIN, WARN } from "@/components/theme";

export const TAGS: Record<string, { c: string; label: string }> = {
  momentum: { c: WIN, label: "momentum" },
  earnings_play: { c: "#8b7bff", label: "earnings play" },
  breakout: { c: "#33d6ea", label: "breakout" },
  hedge: { c: "#8b93a8", label: "hedge" },
  iv_crush: { c: WARN, label: "IV crush" },
  contrarian: { c: "#ff6bd6", label: "contrarian" },
  neutral: { c: "#8b93a8", label: "neutral" },
};

export function tagFor(tag: string | undefined) {
  return TAGS[tag ?? "momentum"] ?? TAGS.momentum;
}
