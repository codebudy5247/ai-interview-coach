interface ScoreRingProps {
  score: number   // 1–10
  size?: number
}

function getColor(score: number): string {
  if (score >= 8) return '#10b981' // emerald
  if (score >= 5) return '#f59e0b' // amber
  return '#f43f5e'                  // rose
}

export default function ScoreRing({ score, size = 120 }: ScoreRingProps) {
  const strokeWidth = 8
  const radius = (size - strokeWidth * 2) / 2
  const circumference = 2 * Math.PI * radius
  const filled = (score / 10) * circumference
  const offset = circumference - filled
  const color = getColor(score)

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      {/* SVG ring — rotated so it starts from the top */}
      <svg
        width={size}
        height={size}
        style={{ transform: 'rotate(-90deg)', display: 'block' }}
        aria-hidden="true"
      >
        {/* background track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#1e293b"
          strokeWidth={strokeWidth}
        />
        {/* score arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>

      {/* centered score label */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 2,
        }}
      >
        <span
          style={{
            fontSize: size * 0.28,
            fontWeight: 700,
            color,
            lineHeight: 1,
            fontFamily: 'Inter, sans-serif',
          }}
        >
          {score}
        </span>
        <span style={{ fontSize: size * 0.13, color: '#64748b', lineHeight: 1 }}>
          /10
        </span>
      </div>
    </div>
  )
}
