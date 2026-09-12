/**
 * ZARO brand artwork — a cohesive "architectural drafting" illustration
 * language used wherever photography is not yet available.
 *
 * Every piece shares the same field lighting, line system and palette so the
 * site reads as one photoshoot. Replacements: drop real photography into
 * `public/images/` and use <BrandPhoto name="..."/> (see src/content/brand-images.ts).
 */

export type ArtworkVariant =
  | "chair"
  | "table"
  | "metalwork"
  | "interior"
  | "workshop"
  | "piece";

const LINE = {
  graphite: "#2a2a26",
  graphiteSoft: "rgba(42,42,38,0.45)",
  guide: "rgba(28,29,27,0.10)",
  ivory: "#e9e3d7",
  ivorySoft: "rgba(233,227,215,0.42)",
  guideLight: "rgba(242,238,230,0.12)",
  bronze: "#a87952",
  bronzeLight: "#c49a71",
};

type Palette = {
  field: string;
  field2: string;
  field3: string;
  ink: string;
  inkSoft: string;
  guide: string;
  accent: string;
  watermark: string;
};

const P: Record<"light" | "dark", Palette> = {
  light: {
    field: "#faf7f1",
    field2: "#f2eee6",
    field3: "#e8e2d6",
    ink: LINE.graphite,
    inkSoft: LINE.graphiteSoft,
    guide: LINE.guide,
    accent: LINE.bronze,
    watermark: "rgba(28,29,27,0.32)",
  },
  dark: {
    field: "#2b2b26",
    field2: "#1f201d",
    field3: "#151611",
    ink: LINE.ivory,
    inkSoft: LINE.ivorySoft,
    guide: LINE.guideLight,
    accent: LINE.bronzeLight,
    watermark: "rgba(242,238,230,0.34)",
  },
};

function FramingGuides({ g }: { g: Palette }) {
  return (
    <g stroke={g.guide} strokeWidth={1} fill="none">
      <circle cx={500} cy={560} r={300} />
      <circle cx={500} cy={560} r={380} />
      <path d="M500 60v880M150 560h700" />
    </g>
  );
}

function Dimension({ y, x1, x2, g }: { y: number; x1: number; x2: number; g: Palette }) {
  return (
    <g stroke={g.inkSoft} strokeWidth={2} fill="none">
      <path d={`M${x1} ${y}h${x2 - x1}`} />
      <path d={`M${x1} ${y - 12}l-7 12 7 12M${x2} ${y - 12}l7 12-7 12`} />
    </g>
  );
}

function artChair(g: Palette) {
  return (
    <g stroke={g.ink} strokeWidth={2.5} fill="none" strokeLinecap="round">
      {/* sculptural back */}
      <path d="M620 640c8-90 20-210 34-272" />
      <path d="M336 640c-12-96-26-180-34-230" />
      <path d="M302 410c-34 12-56 26-66 44 8 18 34 26 66 24" />
      <path d="M654 368c32 8 52 20 60 36-8 18-30 28-60 28" />
      {/* seat */}
      <path d="M306 640h318" strokeWidth={4} />
      <path d="M300 640c-10 26-8 46 4 60 14 16 34 20 52 14" strokeWidth={2.5} />
      {/* legs */}
      <path d="M318 660c-6 58-9 108-8 168" strokeWidth={2} />
      <path d="M622 660c6 58 8 108 8 168" strokeWidth={2} />
      {/* hatching */}
      <g strokeWidth={1.5} opacity={0.6}>
        <path d="M346 700l34-28M446 700l34-28M546 700l34-28M356 752l34-28M456 752l34-28M376 806l32-28" />
      </g>
      {/* accent seam */}
      <path d="M472 660v168" stroke={g.accent} strokeWidth={2.5} />
    </g>
  );
}

function artTable(g: Palette) {
  return (
    <g stroke={g.ink} strokeWidth={2.5} fill="none" strokeLinecap="round">
      {/* top */}
      <path d="M150 430h700" strokeWidth={4} />
      <path d="M150 452h700" strokeWidth={2} />
      <path d="M150 430v22M850 430v22" strokeWidth={2} />
      {/* legs */}
      <path d="M226 452c-4 64-8 128-10 188" strokeWidth={2.5} />
      <path d="M774 452c4 64 8 128 10 188" strokeWidth={2.5} />
      <path d="M232 452c36 40 40 120 34 260-8 4-14 4-16-2" strokeWidth={1.5} opacity={0.7} />
      <path d="M768 452c-36 40-40 120-34 260" strokeWidth={1.5} opacity={0.7} />
      {/* stretcher */}
      <path d="M216 712c64 18 128 20 192 10s128-20 196-28" strokeWidth={2} />
      <path d="M232 560l-6 208M770 560l6 208" stroke={g.guide} strokeWidth={1} />
      {/* accent */}
      <path d="M216 712c6-14 16-22 30-24" stroke={g.accent} strokeWidth={3} />
    </g>
  );
}

function artMetalwork(g: Palette) {
  const grid = (
    <g stroke={g.guide} strokeWidth={1}>
      <path d="M140 160h720M140 340h720M140 520h720M140 700h720" />
      <path d="M330 60v760M500 60v760M670 60v760M140 60v840M860 60v840" />
    </g>
  );
  return (
    <g>
      {grid}
      <g stroke={g.ink} strokeWidth={2.5} fill="none" strokeLinecap="round" strokeLinejoin="round">
        {/* bench line */}
        <path d="M120 716h760" strokeWidth={4} />
        {/* steel bracket */}
        <path d="M330 716V380h330v336" strokeWidth={4} />
        <path d="M330 380h330" strokeWidth={1.5} opacity={0.5} />
        {/* bolt circles */}
        <g strokeWidth={2}>
          <circle cx={396} cy={452} r={17} />
          <circle cx={396} cy={560} r={17} />
          <circle cx={494} cy={636} r={17} />
          <path d="M360 452h-40M360 560h-40M494 636h-40" strokeWidth={3} />
        </g>
        {/* weld bead */}
        <path
          d="M660 400c2 12-8 22 4 34s2 22 6 34"
          stroke={g.accent}
          strokeWidth={3}
        />
        {/* clamp + stock */}
        <path d="M722 636v80M848 636v80M740 636h96M740 716h96" strokeWidth={3} />
        <path d="M740 596h96l-8 40h-80z" strokeWidth={2} />
      </g>
    </g>
  );
}

function artInterior(g: Palette) {
  return (
    <g>
      <g stroke={g.ink} strokeWidth={2.5} fill="none" strokeLinecap="round">
        {/* wall + floor */}
        <path d="M80 430h840M80 430v430" strokeWidth={3} />
        <path d="M80 786h840" strokeWidth={3} />
        {/* arched window */}
        <path d="M150 430v-150a95 95 0 0 1 190 0v150" strokeWidth={3} />
        <path d="M245 185v245M150 330h190M150 292h190" strokeWidth={1.5} opacity={0.7} />
        {/* pendant light */}
        <path d="M470 60v180" strokeWidth={2} />
        <path d="M430 252h80" strokeWidth={4} />
        <path d="M436 252c-4 40-6 70-10 92M494 252c4 40 6 70 10 92" stroke={g.guide} strokeWidth={1.5} />
        {/* lounge chair */}
        <g transform="translate(120 0)">
          <path d="M520 660c0-96-26-252-30-288 24-14 56-16 84-8" strokeWidth={3} />
          <path d="M574 364c-2 60-10 160-24 296" strokeWidth={3} />
          <path d="M520 660h-200c-8 0-14 6-14 16v110" strokeWidth={3} />
          <path d="M574 660h170c8 0 14 8 12 20l-10 106" strokeWidth={3} />
          <path d="M306 660c18 26 18 96 0 170M744 660c-18 26-18 96 0 170" strokeWidth={2.5} />
          <path d="M520 556c-2 26 0 52 6 82" strokeWidth={1.5} opacity={0.6} />
        </g>
        {/* side table + vase */}
        <g transform="translate(60 40)">
          <path d="M746 560h-120M654 630h104" strokeWidth={2.5} />
          <path d="M656 560v-36h92v36" strokeWidth={2} />
          <path d="M702 530c-2-8 2-20-2-30" strokeWidth={1.5} />
          <circle cx={700} cy={506} r={7} strokeWidth={1.5} />
          <path d="M686 500c10 6 18 10 28 12" stroke={g.guide} strokeWidth={1} />
        </g>
        {/* rug */}
        <path d="M300 900c90-14 320-12 420 4-110 8-330 10-420-4z" strokeWidth={2} opacity={0.7} />
      </g>
    </g>
  );
}

function artWorkshop(g: Palette) {
  return (
    <g>
      <g stroke={g.guide} strokeWidth={1} fill="none">
        <circle cx={560} cy={470} r={150} />
        <circle cx={560} cy={470} r={230} />
        <path d="M560 180v580M310 470h500" />
      </g>
      <g stroke={g.ink} strokeWidth={2.5} fill="none" strokeLinecap="round" strokeLinejoin="round">
        {/* bench */}
        <path d="M120 716h760" strokeWidth={4} />
        {/* clamped stock */}
        <path d="M640 588h176v128H640z" strokeWidth={3} />
        <path d="M640 588c20-18 56-22 92-24M732 588v-24M748 588v-24" strokeWidth={2} />
        {/* torch body */}
        <path d="M120 760c60-40 120-70 176-96 26-12 46-26 66-44" strokeWidth={5} />
        <path d="M196 604c-16 8-26 24-30 48M300 596c-18 6-30 18-38 36" strokeWidth={3} />
        {/* nozzle */}
        <path d="M500 480c20-8 42-10 62-6" strokeWidth={6} />
        {/* flame + spatter */}
        <path
          d="M562 474c-4 10 2 18 6 28 8-10 4-20 0-28z"
          stroke={g.accent}
          strokeWidth={2.5}
          fill={g.accent}
          opacity={0.85}
        />
        <g stroke={g.accent} strokeWidth={2} opacity={0.9}>
          <path d="M586 452l6-12M600 466l10-8M592 492l10 10" />
        </g>
      </g>
    </g>
  );
}

function artPiece(g: Palette) {
  return (
    <g stroke={g.ink} strokeWidth={2.5} fill="none" strokeLinecap="round">
      {/* sled-base lounge chair */}
      <path d="M360 700c-6-130-18-262-12-320" strokeWidth={3} />
      <path d="M348 380c-40 6-64 22-72 46 6 22 30 34 66 36" strokeWidth={2.5} />
      <path d="M662 700c6-130 18-262 12-320" strokeWidth={3} />
      <path d="M674 380c40 6 64 22 72 46-6 22-30 34-66 36" strokeWidth={2.5} />
      <path d="M348 700h314" strokeWidth={4} />
      <path d="M324 700c-26 30-34 78-26 140" strokeWidth={2.5} />
      <path d="M686 700c26 30 34 78 26 140" strokeWidth={2.5} />
      <path d="M352 516c52-14 196-14 248 0-30 16-68 20-124 20s-94-4-124-20z" strokeWidth={2} opacity={0.85} />
      <path d="M400 468c60-16 100-16 160 0" stroke={g.guide} strokeWidth={1.5} />
      <path d="M380 840h200M390 854h180" strokeWidth={1.5} opacity={0.5} />
      {/* accent */}
      <path d="M448 700v140M552 700v140" stroke={g.accent} strokeWidth={2} opacity={0.9} />
    </g>
  );
}

const DRAW: Record<ArtworkVariant, (g: Palette) => React.ReactNode> = {
  chair: artChair,
  table: artTable,
  metalwork: artMetalwork,
  interior: artInterior,
  workshop: artWorkshop,
  piece: artPiece,
};

export default function FurnitureArtwork({
  variant,
  tone = "light",
  className = "",
  watermark = false,
  ariaLabel,
}: {
  variant: ArtworkVariant;
  tone?: "light" | "dark";
  className?: string;
  watermark?: boolean;
  ariaLabel?: string;
}) {
  const g = P[tone];
  const field = (
    <radialGradient id={`zg-${variant}-${tone}`} cx="24%" cy="14%" r="110%">
      <stop offset="0%" stopColor={g.field} />
      <stop offset="46%" stopColor={g.field2} />
      <stop offset="100%" stopColor={g.field3} />
    </radialGradient>
  );

  return (
    <div className={`artfield grain ${tone === "dark" ? "artfield-dark" : ""} h-full w-full ${className}`}>
      <svg
        viewBox="0 0 1000 1000"
        preserveAspectRatio="xMidYMid slice"
        className="h-full w-full"
        aria-hidden={ariaLabel ? undefined : true}
        role={ariaLabel ? "img" : undefined}
        aria-label={ariaLabel}
      >
        <defs>{field}</defs>
        <rect width="1000" height="1000" fill={`url(#zg-${variant}-${tone})`} />
        <FramingGuides g={g} />
        {DRAW[variant](g)}
        {variant === "table" ? <Dimension y={880} x1={210} x2={790} g={g} /> : null}
        {watermark ? (
          <text
            x="60"
            y="950"
            fill={g.watermark}
            fontFamily="Fraunces, Georgia, serif"
            fontSize="38"
            letterSpacing="16"
          >
            ZARO
          </text>
        ) : null}
      </svg>
      <div className="pointer-events-none absolute inset-0 shadow-[inset_0_1px_0_rgba(255,255,255,0.35),inset_0_-60px_80px_-60px_rgba(11,11,11,0.35)]" />
    </div>
  );
}