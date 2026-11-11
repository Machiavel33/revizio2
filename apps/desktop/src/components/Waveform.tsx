import { useEffect, useRef } from "react";

interface WaveformProps {
  level: number; // 0..1
  active: boolean;
  bars?: number;
}

/**
 * Waveform réactive : barres verticales cyan→violet dont la hauteur suit le
 * niveau audio. Signature visuelle de Revizio.
 */
export default function Waveform({ level, active, bars = 48 }: WaveformProps) {
  const heights = useRef<number[]>(Array(bars).fill(0.05));

  useEffect(() => {
    // Décale l'historique et ajoute le niveau courant avec un léger aléa
    const next = heights.current.slice(1);
    const jitter = active ? level * (0.6 + Math.random() * 0.4) : 0.05;
    next.push(Math.max(0.05, Math.min(1, jitter)));
    heights.current = next;
  }, [level, active]);

  return (
    <div className="flex h-24 items-center justify-center gap-1">
      {heights.current.map((h, i) => {
        const ratio = i / bars;
        const color = `hsl(${190 + ratio * 90}, 100%, 60%)`;
        return (
          <div
            key={i}
            className="w-1.5 rounded-full transition-[height] duration-75"
            style={{
              height: `${Math.max(6, h * 96)}px`,
              background: active ? color : "var(--border-strong)",
              opacity: active ? 0.9 : 0.4,
            }}
          />
        );
      })}
    </div>
  );
}
