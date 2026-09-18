const FONT = 'Arial, Helvetica, sans-serif';

const C = {
  ink: '#1D2528',
  paper: '#FCFBF7',
  yellow: '#C7B56E',
  yellowStroke: '#675B2D',
  yellowIcon: '#274B5C',
  blue: '#7FA49D',
  blueStroke: '#355F59',
  blueIcon: '#6B3038',
  green: '#B09CAF',
  greenStroke: '#624E63',
  greenIcon: '#245B57',
  question: '#C98E78',
  questionStroke: '#704536',
  questionText: '#243F4A',
  success: '#2F765C',
  red: '#A33B35',
  divider: '#77736B',
};

type Point = { x: number; y: number };
type BlockProps = Point & {
  width: number;
  height: number;
  fill: string;
  stroke: string;
  children: any;
};

function Block({ x, y, width, height, fill, stroke, children }: BlockProps) {
  const notch = 8;
  const shape = [
    `M ${x + notch} ${y}`,
    `H ${x + width - notch}`,
    `L ${x + width} ${y + notch}`,
    `V ${y + height - notch}`,
    `L ${x + width - notch} ${y + height}`,
    `H ${x + notch}`,
    `L ${x} ${y + height - notch}`,
    `V ${y + notch}`,
    'Z',
  ].join(' ');

  return (
    <g>
      <path d={shape} fill={fill} stroke={stroke} strokeWidth="1.6" strokeLinejoin="round" />
      {children}
    </g>
  );
}

function Arrow({ x1, y1, x2, y2 }: { x1: number; y1: number; x2: number; y2: number }) {
  return (
    <line
      x1={x1}
      y1={y1}
      x2={x2}
      y2={y2}
      stroke={C.ink}
      strokeWidth="2.2"
      strokeLinecap="round"
      markerEnd="url(#arrowhead)"
    />
  );
}

function SectionTitle({ x, number, title, subtitle }: { x: number; number: string; title: string; subtitle: string }) {
  return (
    <g>
      <circle cx={x + 15} cy="39" r="15" fill={C.paper} stroke={C.ink} strokeWidth="2" />
      <text
        x={x + 15}
        y="46"
        textAnchor="middle"
        fontFamily={FONT}
        fontSize="19"
        fontWeight="600"
        fill={C.ink}
      >
        {number}
      </text>
      <text x={x + 42} y="48" fontFamily={FONT} fontSize="27" fontWeight="600" fill={C.ink}>
        {title}
      </text>
      <text x={x + 228} y="94" textAnchor="middle" fontFamily={FONT} fontSize="19" fontWeight="600" fill={C.ink}>
        {subtitle}
      </text>
    </g>
  );
}

function QuestionBox({ x, y }: Point) {
  const shape = `M ${x + 7} ${y} H ${x + 63} L ${x + 70} ${y + 7} V ${y + 57} L ${x + 63} ${y + 64} H ${x + 7} L ${x} ${y + 57} V ${y + 7} Z`;

  return (
    <g>
      <path d={shape} fill={C.question} stroke={C.questionStroke} strokeWidth="1.8" strokeLinejoin="round" />
      <text
        x={x + 35}
        y={y + 42}
        textAnchor="middle"
        fontFamily={FONT}
        fontSize="28"
        fontWeight="600"
        fill={C.questionText}
      >
        Q
      </text>
    </g>
  );
}

function CodeIcon({ x, y }: Point) {
  return (
    <g
      transform={`translate(${x} ${y})`}
      fill="none"
      stroke={C.yellowIcon}
      strokeWidth="2.1"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M-14 -17 H7 L14 -10 V17 H-14 Z" />
      <path d="M7 -17 V-10 H14" />
      <path d="M-6 -3 L-10 1 L-6 5 M3 -3 L7 1 L3 5" />
    </g>
  );
}

function TerminalIcon({ x, y }: Point) {
  return (
    <g
      transform={`translate(${x} ${y})`}
      fill="none"
      stroke={C.blueIcon}
      strokeWidth="2.1"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="-17" y="-13" width="34" height="26" rx="2" />
      <path d="M-10 -4 L-5 0 L-10 4 M0 5 H9" />
    </g>
  );
}

function ShieldIcon({ x, y }: Point) {
  return (
    <g
      transform={`translate(${x} ${y})`}
      fill="none"
      stroke={C.greenIcon}
      strokeWidth="2.1"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M0 -17 L14 -12 V-1 C14 8 8 14 0 18 C-8 14 -14 8 -14 -1 V-12 Z" />
      <path d="M-7 0 L-2 5 L8 -6" />
    </g>
  );
}

function DocumentIcon({ x, y }: Point) {
  return (
    <g
      transform={`translate(${x} ${y})`}
      fill="none"
      stroke={C.blueIcon}
      strokeWidth="2.1"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M-13 -17 H6 L13 -10 V17 H-13 Z" />
      <path d="M6 -17 V-10 H13 M-6 -4 H7 M-6 2 H7 M-6 8 H2" />
    </g>
  );
}

function CompareIcon({ x, y }: Point) {
  return (
    <g
      transform={`translate(${x} ${y})`}
      fill="none"
      stroke={C.greenIcon}
      strokeWidth="2.1"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="-8" cy="0" r="9" />
      <circle cx="8" cy="0" r="9" />
      <path d="M-2 -14 H10 L7 -17 M2 14 H-10 L-7 17" />
    </g>
  );
}

function SolverIcon({ x, y }: Point) {
  return (
    <g
      transform={`translate(${x} ${y})`}
      fill="none"
      stroke={C.blueIcon}
      strokeWidth="2.1"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="-14" y="-14" width="28" height="28" rx="2" />
      <path d="M-19 -7 H-14 M-19 0 H-14 M-19 7 H-14 M14 -7 H19 M14 0 H19 M14 7 H19" />
      <path d="M-7 -19 V-14 M0 -19 V-14 M7 -19 V-14 M-7 14 V19 M0 14 V19 M7 14 V19" />
      <path d="M-7 -6 H7 L-6 7 H8" />
    </g>
  );
}

function EvidenceIcon({ x, y }: Point) {
  return (
    <g
      transform={`translate(${x} ${y})`}
      fill="none"
      stroke={C.greenIcon}
      strokeWidth="2.1"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="-13" cy="0" r="5" fill={C.paper} />
      <circle cx="0" cy="0" r="5" fill={C.paper} />
      <circle cx="13" cy="0" r="5" fill={C.paper} />
      <path d="M-8 0 H-5 M5 0 H8" />
    </g>
  );
}

function LlmProgram({ x }: { x: number }) {
  return (
    <>
      <QuestionBox x={x + 30} y={128} />
      <Arrow x1={x + 100} y1={160} x2={x + 140} y2={160} />
      <Block x={x + 150} y={120} width={300} height={80} fill={C.yellow} stroke={C.yellowStroke}>
        <CodeIcon x={x + 190} y={160} />
        <text x={x + 315} y="153" textAnchor="middle" fontFamily={FONT} fontSize="22" fontWeight="600" fill={C.ink}>
          LLM
        </text>
        <text x={x + 315} y="180" textAnchor="middle" fontFamily={FONT} fontSize="22" fontWeight="600" fill={C.ink}>
          Program
        </text>
      </Block>
    </>
  );
}

function ResultMarks({ centerX }: { centerX: number }) {
  return (
    <g fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d={`M${centerX - 94} 533 L${centerX - 82} 547 L${centerX - 55} 513`} stroke={C.success} strokeWidth="8" />
      <path d={`M${centerX + 55} 519 L${centerX + 83} 547 M${centerX + 83} 519 L${centerX + 55} 547`} stroke={C.red} strokeWidth="8" />
    </g>
  );
}

export default function App() {
  return (
    <div
      style={{
        width: '100%',
        background: C.paper,
        display: 'flex',
        justifyContent: 'center',
        padding: '20px',
        boxSizing: 'border-box',
      }}
    >
      <svg
        viewBox="0 0 1560 680"
        style={{ width: '100%', maxWidth: 1560, height: 'auto', display: 'block' }}
        role="img"
        aria-labelledby="degro-figure-title degro-figure-desc"
      >
        <title id="degro-figure-title">Execution, outcome, and determinacy-level evaluation</title>
        <desc id="degro-figure-desc">
          Three evaluation pipelines compare program execution, answer matching, and DeGro target-determinacy diagnosis. DeGro identifies two feasible models with different target values and leads to grounded repair or abstention.
        </desc>

        <defs>
          <marker id="arrowhead" markerWidth="9" markerHeight="8" refX="8" refY="4" orient="auto">
            <path d="M0 0 L9 4 L0 8" fill="none" stroke={C.ink} strokeWidth="1.6" />
          </marker>
        </defs>

        <rect width="1560" height="680" fill={C.paper} />
        <line x1="520" y1="20" x2="520" y2="660" stroke={C.divider} strokeWidth="1.5" strokeDasharray="2 6" />
        <line x1="1040" y1="20" x2="1040" y2="660" stroke={C.divider} strokeWidth="1.5" strokeDasharray="2 6" />

        <SectionTitle x={32} number="1" title="Execution-level" subtitle="Program execution" />
        <LlmProgram x={0} />
        <Arrow x1={300} y1={200} x2={300} y2={247} />
        <Block x={55} y={258} width={410} height={62} fill={C.blue} stroke={C.blueStroke}>
          <TerminalIcon x={98} y={289} />
          <text x="277" y="297" textAnchor="middle" fontFamily={FONT} fontSize="21" fontWeight="600" fill={C.ink}>
            Execute Program
          </text>
        </Block>
        <Arrow x1={260} y1={320} x2={260} y2={366} />
        <Block x={55} y={378} width={410} height={62} fill={C.green} stroke={C.greenStroke}>
          <ShieldIcon x={98} y={409} />
          <text x="277" y="417" textAnchor="middle" fontFamily={FONT} fontSize="21" fontWeight="600" fill={C.ink}>
            Runtime Check
          </text>
        </Block>
        <Arrow x1={260} y1={440} x2={260} y2={492} />
        <ResultMarks centerX={260} />
        <text x="260" y="610" textAnchor="middle" fontFamily={FONT} fontSize="23" fontWeight="600" fill={C.ink}>
          Runs / Fails
        </text>

        <SectionTitle x={552} number="2" title="Outcome-level" subtitle="Answer matching" />
        <LlmProgram x={520} />
        <Arrow x1={820} y1={200} x2={820} y2={247} />
        <Block x={575} y={258} width={410} height={62} fill={C.blue} stroke={C.blueStroke}>
          <DocumentIcon x={618} y={289} />
          <text x="797" y="297" textAnchor="middle" fontFamily={FONT} fontSize="21" fontWeight="600" fill={C.ink}>
            Extract Answer
          </text>
        </Block>
        <Arrow x1={780} y1={320} x2={780} y2={366} />
        <Block x={575} y={378} width={410} height={62} fill={C.green} stroke={C.greenStroke}>
          <CompareIcon x={618} y={409} />
          <text x="797" y="417" textAnchor="middle" fontFamily={FONT} fontSize="21" fontWeight="600" fill={C.ink}>
            Answer Matching
          </text>
        </Block>
        <Arrow x1={780} y1={440} x2={780} y2={492} />
        <ResultMarks centerX={780} />
        <text x="780" y="610" textAnchor="middle" fontFamily={FONT} fontSize="23" fontWeight="600" fill={C.ink}>
          Correct / Incorrect
        </text>

        <SectionTitle x={1072} number="3" title="Determinacy-level" subtitle="DeGro (Ours)" />
        <LlmProgram x={1040} />
        <Arrow x1={1340} y1={200} x2={1340} y2={247} />
        <Block x={1095} y={258} width={410} height={62} fill={C.blue} stroke={C.blueStroke}>
          <SolverIcon x={1138} y={289} />
          <text x="1325" y="297" textAnchor="middle" fontFamily={FONT} fontSize="20" fontWeight="600" fill={C.ink}>
            Target Determinacy Check
          </text>
        </Block>
        <Arrow x1={1300} y1={320} x2={1300} y2={354} />
        <Block x={1105} y={366} width={138} height={58} fill={C.paper} stroke={C.blueStroke}>
          <text x="1174" y="403" textAnchor="middle" fontFamily={FONT} fontSize="23" fontWeight="600" fill={C.ink}>
            q = 4
          </text>
        </Block>
        <text x="1300" y="405" textAnchor="middle" fontFamily={FONT} fontSize="30" fontWeight="600" fill={C.red}>
          ≠
        </text>
        <Block x={1357} y={366} width={138} height={58} fill={C.paper} stroke={C.blueStroke}>
          <text x="1426" y="403" textAnchor="middle" fontFamily={FONT} fontSize="23" fontWeight="600" fill={C.ink}>
            q = 6
          </text>
        </Block>
        <text x="1300" y="461" textAnchor="middle" fontFamily={FONT} fontSize="18" fontWeight="500" fill={C.ink}>
          Two feasible models
        </text>
        <Arrow x1={1300} y1={472} x2={1300} y2={518} />
        <Block x={1095} y={530} width={410} height={62} fill={C.green} stroke={C.greenStroke}>
          <EvidenceIcon x={1138} y={561} />
          <text x="1325" y="569" textAnchor="middle" fontFamily={FONT} fontSize="20" fontWeight="600" fill={C.ink}>
            Grounded Repair / Abstain
          </text>
        </Block>
      </svg>
    </div>
  );
}
