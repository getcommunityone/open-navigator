import {makeScene2D, Rect, Txt} from '@canvas-commons/2d';
import {
  all,
  createRef,
  easeOutBack,
  sequence,
  waitFor,
} from '@canvas-commons/core';
import {DECISION} from '../decision';
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
  view.add(makeBackground(COLORS.yellow));

  const header = createRef<Rect>();
  const q = createRef<Txt>();
  const bar = createRef<Rect>();
  const label = createRef<Txt>();

  const cA = createRef<Rect>();
  const cB = createRef<Rect>();
  const cC = createRef<Rect>();
  const cD = createRef<Rect>();

  const board = createRef<Rect>();

  view.add(
    <>
      <Rect
        ref={header}
        y={-780}
        width={820}
        height={104}
        radius={16}
        fill={COLORS.red}
        rotation={-1.5}
        opacity={0}
        scale={0}
        alignItems={'center'}
        justifyContent={'center'}
      >
        <Txt
          text="FINAL ANSWER · THE VOTE"
          fontFamily={DISPLAY}
          fontWeight={900}
          fontSize={46}
          fill={COLORS.white}
          letterSpacing={1}
        />
      </Rect>
      <Txt
        ref={q}
        text="So… how did this circus actually end?"
        y={-560}
        width={940}
        textAlign={'center'}
        textWrap
        fontFamily={BODY}
        fontWeight={800}
        fontSize={56}
        fill={COLORS.white}
        opacity={0}
      />
      {AnswerChip({ref: cA, letter: 'A', text: 'Denied', y: -300, accent: COLORS.magenta})}
      {AnswerChip({ref: cB, letter: 'B', text: 'Tabled for later', y: -120, accent: COLORS.magenta})}
      {AnswerChip({
        ref: cC,
        letter: 'C',
        text: 'Approved 8 – 1',
        y: 60,
        accent: COLORS.magenta,
      })}
      {AnswerChip({
        ref: cD,
        letter: 'D',
        text: 'Unanimous 9 – 0',
        y: 240,
        accent: COLORS.magenta,
      })}

      <Rect
        ref={board}
        y={-60}
        width={960}
        height={520}
        radius={28}
        fill={COLORS.ink}
        stroke={COLORS.yellow}
        lineWidth={6}
        opacity={0}
        scale={0}
        layout
        alignItems={'center'}
        justifyContent={'center'}
        gap={50}
        shadowColor={'#000000aa'}
        shadowBlur={30}
      >
        <Rect direction={'column'} alignItems={'center'} gap={6}>
          <Txt text="YES" fontFamily={DISPLAY} fontWeight={900} fontSize={64} fill={COLORS.green} />
          <Txt
            text={`${DECISION.vote.yes}`}
            fontFamily={DISPLAY}
            fontWeight={900}
            fontSize={260}
            fill={COLORS.green}
          />
        </Rect>
        <Txt text="–" fontFamily={DISPLAY} fontWeight={900} fontSize={180} fill={COLORS.dim} />
        <Rect direction={'column'} alignItems={'center'} gap={6}>
          <Txt text="NO" fontFamily={DISPLAY} fontWeight={900} fontSize={64} fill={COLORS.red} />
          <Txt
            text={`${DECISION.vote.no}`}
            fontFamily={DISPLAY}
            fontWeight={900}
            fontSize={260}
            fill={COLORS.red}
          />
        </Rect>
      </Rect>

      {HostBar({barRef: bar, labelRef: label})}
    </>,
  );

  sfx('pop');
  yield* all(header().scale(1, 0.5, easeOutBack), header().opacity(1, 0.35));
  yield* q().opacity(1, 0.4);
  yield* sequence(
    0.16,
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

  yield* say(bar, label, 'No drumroll budget. Just pick one.');
  yield* waitFor(3.0);

  sfx('ding');
  yield* all(
    cA().opacity(0.3, 0.3),
    cB().opacity(0.3, 0.3),
    cD().opacity(0.3, 0.3),
    markCorrect(cC),
  );
  yield* say(bar, label, 'Approved — 8 to 1. It passed anyway.');
  yield* waitFor(3.0);

  // Swap the quiz for the scoreboard.
  yield* all(
    q().opacity(0, 0.3),
    cA().opacity(0, 0.3),
    cB().opacity(0, 0.3),
    cC().opacity(0, 0.3),
    cD().opacity(0, 0.3),
  );
  sfx('boom');
  yield* all(board().scale(1, 0.5, easeOutBack), board().opacity(1, 0.35));
  yield* say(bar, label, `${DECISION.dissenter} cast the lone NO. Respect the holdout.`);
  yield* waitFor(4.5);

  sfx('whoosh');
  yield* all(
    header().opacity(0, 0.4),
    board().opacity(0, 0.4),
    bar().opacity(0, 0.4),
  );
});
