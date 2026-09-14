const FONT = "'Trebuchet MS', Arial, sans-serif";

const C = {
  ink: "#252B33",
  paper: "#FBFAF7",
  context: "#DDB6CF",
  contextCard: "#F0DCE8",
  purple: "#CBBCE0",
  purpleCard: "#E6DDF0",
  blue: "#B8D3E8",
  blueStrong: "#4E91C9",
  blueCard: "#DCEBF5",
  peach: "#E7C3A7",
  green: "#A9D5AE",
  amber: "#E8CF55",
  red: "#DEA0A0",
  gray: "#D9D8D2",
  iconPink: "#B52F68",
  iconPurple: "#6741A5",
  iconBlue: "#1F6FA8",
  iconGold: "#A46808",
  iconGreen: "#167653",
  iconRed: "#B63B3B",
};

type IconName = "problem" | "brain" | "python" | "model" | "solver" | "repair" | "check" | "warning";

function Icon({ name, x, y, color }: { name: IconName; x: number; y: number; color: string }) {
  const p = { fill: "none", stroke: color, strokeWidth: 2.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return <g transform={`translate(${x},${y})`} {...p}>
    {name === "problem" && <><path d="M-15-20H3l12 12v28h-30z" /><path d="M3-20v13h12M-8 3H8M-8 12H5" /></>}
    {name === "brain" && <><path d="M-2-19c-8-5-15 2-12 10-6 4-3 13 4 13-2 8 8 12 10 5" /><path d="M2-19c8-5 15 2 12 10 6 4 3 13-4 13 2 8-8 12-10 5M0-19v34M-9-6h6M9-6H3" /></>}
    {name === "python" && <><path d="M-2-19c-11 0-14 5-14 12v6H2v6h-22c-6 0-9 5-9 12" /><path d="M2 19c11 0 14-5 14-12V1H-2v-6h22c6 0 9-5 9-12" /><circle cx="-8" cy="-12" r="1.5" fill={color} /><circle cx="8" cy="12" r="1.5" fill={color} /></>}
    {name === "model" && <><circle cy="-16" r="5" /><circle cx="-17" cy="13" r="5" /><circle cx="17" cy="13" r="5" /><path d="M-3-12-14 9M3-12l11 21M-12 13h24" /></>}
    {name === "solver" && <><rect x="-19" y="-17" width="38" height="34" rx="3" /><path d="M-11-9h6M3-9h9M-11 0h6M3 0h9M-11 9h23" /></>}
    {name === "repair" && <><path d="M-18 12h36M-13 12V0h10v12M3 12V-11h10v23" /><path d="M0-19v12M-6-13H6" /></>}
    {name === "check" && <><circle r="19" /><path d="m-9 0 6 7 13-14" /></>}
    {name === "warning" && <><path d="m0-20 20 35h-40z" /><path d="M0-9V5M0 11v1" /></>}
  </g>;
}

function Panel({ x, y, w, h, title, fill }: { x: number; y: number; w: number; h: number; title: string; fill: string }) {
  return <g>
    <rect x={x} y={y} width={w} height={h} rx="22" fill={fill} fillOpacity="0.82" stroke={C.ink} strokeWidth="3" />
    <text x={x + 25} y={y + 40} fontFamily={FONT} fontSize="28" fontWeight="700" fill={C.ink}>{title}</text>
  </g>;
}

function Card({ x, y, w, h, title, icon, fill, iconColor }: {
  x: number; y: number; w: number; h: number; title: string; icon: IconName; fill: string; iconColor: string;
}) {
  return <g>
    <rect x={x} y={y} width={w} height={h} rx="9" fill={fill} fillOpacity="0.9" stroke={C.ink} strokeWidth="2.7" />
    <rect x={x + 18} y={y + h / 2 - 27} width="54" height="54" rx="9" fill={iconColor} fillOpacity="0.15" />
    <Icon name={icon} x={x + 45} y={y + h / 2} color={iconColor} />
    <text x={x + 88} y={y + h / 2 + 10} fontFamily={FONT} fontSize="30" fontWeight="700" fill={C.ink}>{title}</text>
  </g>;
}

function Status({ x, y, w, title, fill, dot }: { x: number; y: number; w: number; title: string; fill: string; dot: string }) {
  return <g>
    <rect x={x} y={y} width={w} height="58" rx="8" fill={fill} fillOpacity="0.88" stroke={C.ink} strokeWidth="2.7" />
    <circle cx={x + 33} cy={y + 29} r="13" fill={dot} stroke={C.ink} strokeWidth="2.2" />
    <text x={x + 62} y={y + 39} fontFamily={FONT} fontSize="25" fontWeight="700" fill={C.ink}>{title}</text>
  </g>;
}

function Connector({ d, dashed = false, arrow = true }: { d: string; dashed?: boolean; arrow?: boolean }) {
  return <path d={d} fill="none" stroke={C.ink} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" strokeDasharray={dashed ? "10 9" : undefined} markerEnd={arrow ? "url(#arrow)" : undefined} />;
}

function EdgeLabel({ x, y, text }: { x: number; y: number; text: string }) {
  const width = text.length * 11 + 24;
  return <g>
    <rect x={x - width / 2} y={y - 21} width={width} height="31" rx="4" fill={C.paper} />
    <text x={x} y={y + 1} textAnchor="middle" fontFamily={FONT} fontSize="20" fontWeight="700" fill={C.ink}>{text}</text>
  </g>;
}

function Output({ x, y, w, title, fill, icon, iconColor }: {
  x: number; y: number; w: number; title: string; fill: string; icon: IconName; iconColor: string;
}) {
  return <Card x={x} y={y} w={w} h={90} title={title} fill={fill} icon={icon} iconColor={iconColor} />;
}

export default function App() {
  return <div className="min-h-screen flex items-center justify-center p-8" style={{ background: "#D8D8D3" }}>
    <div style={{ width: "100%", maxWidth: 1800, background: C.paper }}>
      <svg viewBox="0 0 1800 1100" style={{ width: "100%", display: "block" }} role="img" aria-label="SymCode and DeGro pipeline">
        <defs>
          <marker id="arrow" markerWidth="11" markerHeight="9" refX="10" refY="4.5" orient="auto"><path d="M0 0 11 4.5 0 9z" fill={C.ink} /></marker>
        </defs>

        <rect x="20" y="20" width="1760" height="1060" rx="14" fill={C.paper} stroke={C.ink} strokeWidth="2.7" />

        <Panel x={60} y={80} w={300} h={250} title="Problem Context" fill={C.context} />
        <Card x={95} y={145} w={230} h={130} title="Problem" icon="problem" fill={C.contextCard} iconColor={C.iconPink} />

        <Panel x={410} y={80} w={1330} h={250} title="SymCode" fill={C.purple} />
        <Card x={480} y={155} w={400} h={110} title="Generate" icon="brain" fill={C.purpleCard} iconColor={C.iconPurple} />
        <Card x={1200} y={155} w={360} h={110} title="Python Code" icon="python" fill={C.purpleCard} iconColor={C.iconBlue} />

        <Connector d="M325 210 H480" />
        <Connector d="M880 210 H1200" />

        <Panel x={140} y={400} w={1500} h={330} title="DeGro" fill={C.blue} />
        <Card x={210} y={465} w={330} h={100} title="ModelSpec" icon="model" fill={C.blueCard} iconColor={C.iconGold} />

        <rect x="600" y="440" width="560" height="130" rx="11" fill={C.blueStrong} fillOpacity="0.8" stroke={C.ink} strokeWidth="2.7" />
        <text x="628" y="477" fontFamily={FONT} fontSize="25" fontWeight="700" fill={C.paper}>Target Verification</text>
        <Card x={640} y={483} w={480} h={65} title="Z3 Check" icon="solver" fill={C.blueCard} iconColor={C.iconBlue} />

        <Connector d="M540 515 H640" />
        <Connector d="M210 275 V375 H300 V460" />
        <Connector d="M1380 265 V350 H450 V460" />
        <EdgeLabel x={900} y={341} text="Python" />

        <Connector d="M880 548 V610" arrow={false} />
        <Connector d="M400 610 H1370" arrow={false} />
        <Connector d="M400 610 V625" />
        <Connector d="M890 610 V625" />
        <Connector d="M1370 610 V625" />

        <Status x={250} y={630} w={300} title="DETERMINATE" fill={C.green} dot="#25A85A" />
        <Status x={740} y={630} w={300} title="AMBIGUOUS" fill={C.amber} dot="#F4C900" />
        <Status x={1230} y={630} w={280} title="NO VERDICT" fill={C.red} dot="#DF4343" />

        <Output x={230} y={790} w={340} title="Answer" fill={C.green} icon="check" iconColor={C.iconGreen} />
        <Card x={710} y={780} w={360} h={100} title="Grounded Repair" icon="repair" fill={C.peach} iconColor={C.iconGold} />
        <Output x={1210} y={790} w={340} title="No Certificate" fill={C.gray} icon="warning" iconColor={C.iconRed} />

        <Connector d="M400 688 L400 790" />
        <Connector d="M890 688 L890 780" />
        <Connector d="M1370 688 L1370 790" />

        <Connector d="M890 880 L890 920" />
        <polygon points="890,925 1015,970 890,1015 765,970" fill="#F3EEE8" stroke={C.ink} strokeWidth="2.7" />
        <text x="890" y="980" textAnchor="middle" fontFamily={FONT} fontSize="27" fontWeight="700" fill={C.ink}>Valid?</text>

        <Output x={360} y={925} w={300} title="Abstain" fill="#F7DFC8" icon="warning" iconColor={C.iconGold} />
        <Output x={1140} y={925} w={330} title="Repaired" fill={C.green} icon="check" iconColor={C.iconGreen} />
        <Connector d="M765 970 H660" />
        <Connector d="M1015 970 H1140" />
        <EdgeLabel x={712} y={957} text="No" />
        <EdgeLabel x={1078} y={957} text="Yes" />
      </svg>
    </div>
  </div>;
}
