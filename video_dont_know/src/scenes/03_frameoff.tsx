import {Layout, makeScene2D, Rect, Txt} from '@canvas-commons/2d';
import {
  all,
  createRef,
  easeOutBack,
  easeOutCubic,
  Reference,
  sequence,
  waitFor,
} from '@canvas-commons/core';
import {FRAME_AGAINST, FRAME_FOR} from '../decision';
import {BODY, COLORS, DISPLAY, HostBar, makeBackground, say, sfx} from '../lib';

type Frame = typeof FRAME_FOR;

function labeledRow(
  rowRef: Reference<Layout>,
  tag: string,
  tagColor: string,
  text: string,
): Layout {
  return (
    <Layout ref={rowRef} direction={'column'} gap={4} opacity={0}>
      <Txt
        text={tag}
        fontFamily={DISPLAY}
        fontWeight={900}
        fontSize={26}
        fill={tagColor}
        letterSpacing={3}
      />
      <Txt
        text={text}
        fontFamily={BODY}
        fontWeight={600}
        fontSize={36}
        fill={COLORS.white}
        width={880}
        textWrap
      />
    </Layout>
  ) as Layout;
}

function panel(
  panelRef: Reference<Rect>,
  rows: Reference<Layout>[],
  accent: string,
  frame: Frame,
  startY: number,
  targetY: number,
): Rect {
  return (
    <Rect
      ref={panelRef}
      x={0}
      y={startY}
      width={980}
      radius={24}
      fill={'#180a36'}
      stroke={accent}
      lineWidth={5}
      opacity={0}
      layout
      direction={'column'}
      padding={34}
      gap={18}
      shadowColor={'#00000077'}
      shadowBlur={28}
      shadowOffset={[0, 12]}
    >
      <Txt
        text={frame.team}
        fontFamily={DISPLAY}
        fontWeight={900}
        fontSize={44}
        fill={accent}
        letterSpacing={1}
      />
      <Txt
        text={frame.who}
        fontFamily={BODY}
        fontWeight={700}
        fontSize={30}
        fill={COLORS.dim}
      />
      {labeledRow(rows[0], 'THE PROBLEM', accent, frame.problem)}
      {labeledRow(rows[1], 'THE STORY', accent, frame.story)}
      {labeledRow(rows[2], 'THE FIX', accent, frame.remedy)}
    </Rect>
  ) as Rect;
}

export default makeScene2D(function* (view) {
  view.add(makeBackground(COLORS.magenta));

  const header = createRef<Rect>();
  const bar = createRef<Rect>();
  const label = createRef<Txt>();
  const vs = createRef<Rect>();

  const top = createRef<Rect>();
  const bottom = createRef<Rect>();
  const tRows = [createRef<Layout>(), createRef<Layout>(), createRef<Layout>()];
  const bRows = [createRef<Layout>(), createRef<Layout>(), createRef<Layout>()];

  view.add(
    <>
      <Rect
        ref={header}
        y={-840}
        width={680}
        height={104}
        radius={16}
        fill={COLORS.yellow}
        rotation={-1.5}
        opacity={0}
        scale={0}
        alignItems={'center'}
        justifyContent={'center'}
      >
        <Txt
          text="ROUND 2 · FRAME-OFF!"
          fontFamily={DISPLAY}
          fontWeight={900}
          fontSize={48}
          fill={COLORS.ink}
          letterSpacing={2}
        />
      </Rect>

      {panel(top, tRows, COLORS.blue, FRAME_FOR, -1400, -440)}
      {panel(bottom, bRows, COLORS.red, FRAME_AGAINST, 1400, 300)}

      <Rect
        ref={vs}
        width={140}
        height={140}
        radius={70}
        fill={COLORS.magenta}
        stroke={COLORS.white}
        lineWidth={7}
        y={-70}
        opacity={0}
        scale={0}
        alignItems={'center'}
        justifyContent={'center'}
        shadowColor={'#000000aa'}
        shadowBlur={20}
      >
        <Txt
          text="VS"
          fontFamily={DISPLAY}
          fontWeight={900}
          fontSize={64}
          fill={COLORS.white}
        />
      </Rect>

      {HostBar({barRef: bar, labelRef: label})}
    </>,
  );

  sfx('pop');
  yield* all(header().scale(1, 0.5, easeOutBack), header().opacity(1, 0.35));
  yield* say(bar, label, 'Same grant. Two completely different stories.');
  yield* waitFor(2.2);

  // Blue frame drops in from the top, rows cascade.
  sfx('whoosh');
  yield* all(top().y(-440, 0.7, easeOutCubic), top().opacity(1, 0.5));
  yield* sequence(
    0.25,
    tRows[0]().opacity(1, 0.4),
    tRows[1]().opacity(1, 0.4),
    tRows[2]().opacity(1, 0.4),
  );
  yield* waitFor(1.0);
  yield* say(bar, label, "Staff: it's federal money for emergencies. Take it.");
  yield* waitFor(3.5);

  // Red frame rises in from the bottom.
  sfx('whoosh');
  yield* all(bottom().y(300, 0.7, easeOutCubic), bottom().opacity(1, 0.5));
  yield* sequence(
    0.25,
    bRows[0]().opacity(1, 0.4),
    bRows[1]().opacity(1, 0.4),
    bRows[2]().opacity(1, 0.4),
  );
  yield* waitFor(1.0);
  yield* say(bar, label, 'Hernandez: define your terms before you cash the check.');
  yield* waitFor(3.5);

  sfx('vs');
  yield* all(vs().scale(1, 0.5, easeOutBack), vs().opacity(1, 0.35));
  yield* vs().rotation(360, 0.6, easeOutCubic);

  yield* say(bar, label, "The clash in one line: how do you define 'terrorism'?");
  yield* waitFor(4.0);
  yield* say(bar, label, 'Her evidence: 38 active hate groups in AZ — SPLC, 2023.');
  yield* waitFor(4.0);
  yield* say(bar, label, 'Her red line: not one dollar toward ICE.');
  yield* waitFor(4.0);

  sfx('whoosh');
  yield* all(
    header().opacity(0, 0.4),
    top().opacity(0, 0.4),
    bottom().opacity(0, 0.4),
    vs().opacity(0, 0.4),
    bar().opacity(0, 0.4),
  );
});
