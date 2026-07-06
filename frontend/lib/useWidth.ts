"use client";
// Window-width hook matching the prototype's resize-driven breakpoints
// (narrow < 900, mid < 1180).
import { useEffect, useState } from "react";

export function useWidth(): number {
  const [w, setW] = useState(1440);
  useEffect(() => {
    const onResize = () => setW(window.innerWidth);
    window.addEventListener("resize", onResize);
    onResize();
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return w;
}
