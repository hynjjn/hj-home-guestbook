/** 이름 → 7x7 좌우대칭 픽셀 아바타. mockup의 생성 로직을 그대로 옮겼다. */

const PALETTE = [
  "#ff9db4", "#8fd4a8", "#ffd479", "#a6b8f0",
  "#f4a3d8", "#7fd0d8", "#ffb38a", "#c3a8e8",
];

function hash(str: string): number {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

const N = 7;
const HALF = 4;

export function Avatar({ seed, label }: { seed: string; label: string }) {
  let h = hash(seed);
  const fg = PALETTE[h % PALETTE.length];
  const cells: { x: number; y: number }[] = [];

  for (let y = 0; y < N; y++) {
    for (let x = 0; x < HALF; x++) {
      h = (Math.imul(h ^ (y * 31 + x), 16777619) >>> 0);
      if ((h & 3) < 2) continue; // 채울지 말지
      cells.push({ x, y });
      if (x < HALF - 1) cells.push({ x: N - 1 - x, y });
    }
  }

  return (
    <svg
      className="avatar"
      viewBox={`0 0 ${N} ${N}`}
      role="img"
      aria-label={`${label}님의 아바타`}
      style={{ background: "#f2f2f2" }}
    >
      <g fill={fg}>
        {cells.map((c, i) => (
          <rect key={i} x={c.x} y={c.y} width="1" height="1" />
        ))}
      </g>
    </svg>
  );
}
