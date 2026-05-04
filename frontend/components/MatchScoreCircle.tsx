import { cn } from "@/lib/utils";

interface MatchScoreCircleProps {
  score: number;
  size?: number;
  showLabel?: boolean;
}

export function MatchScoreCircle({ score, size = 56, showLabel = true }: MatchScoreCircleProps) {
  const stroke = size < 50 ? 3 : 4;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const color =
    score >= 85 ? "#3DF5C0" : score >= 70 ? "#4D8DFF" : score >= 55 ? "#FFB454" : "#FF5C7A";

  return (
    <div
      className="relative grid place-items-center"
      style={{ width: size, height: size }}
      aria-label={`Match score ${score}%`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          fill="none"
          style={{ filter: `drop-shadow(0 0 6px ${color}60)` }}
        />
      </svg>
      {showLabel && (
        <div
          className={cn(
            "absolute font-mono font-semibold tracking-tight",
            size < 50 ? "text-[11px]" : "text-sm"
          )}
          style={{ color }}
        >
          {score}
        </div>
      )}
    </div>
  );
}
