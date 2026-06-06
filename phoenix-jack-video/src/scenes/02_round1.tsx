import {makeScene2D, Rect, Txt} from '@canvas-commons/2d';
import {
  all,
  createRef,
  easeOutBack,
  sequence,
  waitFor,
} from '@canvas-commons/core';
import {
  AnswerChip,
  BODY,
  COLORS,
  DISPLAY,
  HostBar,
  makeBackground,
  markCorrect,
  popIn,
  say,
  sfx,
} from '../lib';

export default makeScene2D(function* (view) {
  view.add(makeBackground(COLORS.blue));

  const header = createRef<Rect>();
  const q = createRef<Txt>();
  const bar = createRef<Rect>();
  const label = createRef<Txt>();

  const cA = createRef<Rect>();
  const cB = createRef<Rect>();
  const cC = createRef<Rect>();
  const cD = createRef<Rect>();

  view.add(
    <>
      <Rect
        ref={header}
        y={-760}
        width={820}
        height={104}
        radius={16}
        fill={COLORS.cyan}
        rotation={-1.5}
        opacity={0}
        scale={0}
        alignItems={'center'}
        justifyContent={'center'}
      >
        <Txt
          text="ROUND 1 · NAME THAT GRANT"
          fontFamily={DISPLAY}
          fontWeight={900}
          fontSize={42}
          fill={COLORS.ink}
          letterSpacing={1}
        />
      </Rect>
      <Txt
        ref={q}
        text={
          'Phoenix grabbed federal Homeland Security cash from WHICH fiscal year — and kicked off a fight about ICE?'
        }
        y={-470}
        width={940}
        textAlign={'center'}
        textWrap
        fontFamily={BODY}
        fontWeight={800}
        fontSize={56}
        fill={COLORS.white}
        opacity={0}
      />
      {AnswerChip({ref: cA, letter: 'A', text: '2019', y: -150, accent: COLORS.blue})}
      {AnswerChip({ref: cB, letter: 'B', text: '2020', y: 30, accent: COLORS.blue})}
      {AnswerChip({
        ref: cC,
        letter: 'C',
        text: '2022  (reallocated federal funds)',
        y: 210,
        accent: COLORS.blue,
      })}
      {AnswerChip({ref: cD, letter: 'D', text: '2024', y: 390, accent: COLORS.blue})}
      {HostBar({barRef: bar, labelRef: label})}
    </>,
  );

  sfx('pop');
  yield* all(header().scale(1, 0.5, easeOutBack), header().opacity(1, 0.35));
  yield* q().opacity(1, 0.5);

  yield* sequence(
    0.18,
    (function* () {
      sfx('tick');
      yield* popIn(cA);
    })(),
    (function* () {
      sfx('tick');
      yield* popIn(cB);
    })(),
    (function* () {
      sfx('tick');
      yield* popIn(cC);
    })(),
    (function* () {
      sfx('tick');
      yield* popIn(cD);
    })(),
  );

  yield* say(bar, label, 'Tick… tick… lock in your answer.');
  yield* waitFor(3.5);

  // dim the wrong ones, slam the right one
  sfx('ding');
  yield* all(
    cA().opacity(0.35, 0.3),
    cB().opacity(0.35, 0.3),
    cD().opacity(0.35, 0.3),
    markCorrect(cC),
  );
  yield* say(bar, label, 'C — FY 2022. Old money, brand-new controversy.');
  yield* waitFor(4.5);

  sfx('whoosh');
  yield* all(
    header().opacity(0, 0.3),
    q().opacity(0, 0.3),
    cA().opacity(0, 0.3),
    cB().opacity(0, 0.3),
    cC().opacity(0, 0.3),
    cD().opacity(0, 0.3),
    bar().opacity(0, 0.3),
  );
});
