import {makeScene2D, Rect, Txt} from '@canvas-commons/2d';
import {
  all,
  createRef,
  easeOutBack,
  sequence,
  waitFor,
} from '@canvas-commons/core';
import {STATS} from '../decision';
import {BODY, COLORS, DISPLAY, HostBar, makeBackground, say, sfx} from '../lib';

export default makeScene2D(function* (view) {
  view.add(makeBackground(COLORS.cyan));

  const header = createRef<Rect>();
  const bar = createRef<Rect>();
  const label = createRef<Txt>();
  const cards = [createRef<Rect>(), createRef<Rect>(), createRef<Rect>()];
  const accents = [COLORS.cyan, COLORS.magenta, COLORS.yellow];
  const ys = [-560, -40, 480];

  view.add(
    <>
      <Rect
        ref={header}
        y={-820}
        width={860}
        height={104}
        radius={16}
        fill={COLORS.magenta}
        rotation={1.5}
        opacity={0}
        scale={0}
        alignItems={'center'}
        justifyContent={'center'}
      >
        <Txt
          text="ROUND 3 · BY THE NUMBERS"
          fontFamily={DISPLAY}
          fontWeight={900}
          fontSize={44}
          fill={COLORS.ink}
          letterSpacing={1}
        />
      </Rect>
      {STATS.map((s, i) => (
        <Rect
          ref={cards[i]}
          y={ys[i]}
          width={960}
          height={430}
          radius={26}
          fill={'#180a36'}
          stroke={accents[i]}
          lineWidth={5}
          opacity={0}
          scale={0}
          layout
          direction={'column'}
          alignItems={'center'}
          justifyContent={'center'}
          padding={30}
          gap={10}
          shadowColor={'#00000077'}
          shadowBlur={26}
          shadowOffset={[0, 12]}
        >
          <Txt
            text={s.big}
            fontFamily={DISPLAY}
            fontWeight={900}
            fontSize={150}
            fill={accents[i]}
          />
          <Txt
            text={s.small}
            fontFamily={BODY}
            fontWeight={600}
            fontSize={38}
            fill={COLORS.white}
            width={840}
            textAlign={'center'}
            textWrap
          />
        </Rect>
      ))}
      {HostBar({barRef: bar, labelRef: label})}
    </>,
  );

  sfx('pop');
  yield* all(header().scale(1, 0.5, easeOutBack), header().opacity(1, 0.35));
  yield* say(bar, label, 'Lightning round — the receipts.');
  yield* sequence(
    0.45,
    (function* () {
      sfx('pop');
      yield* all(cards[0]().scale(1, 0.45, easeOutBack), cards[0]().opacity(1, 0.3));
    })(),
    (function* () {
      sfx('pop');
      yield* all(cards[1]().scale(1, 0.45, easeOutBack), cards[1]().opacity(1, 0.3));
    })(),
    (function* () {
      sfx('boom', -4);
      yield* all(cards[2]().scale(1, 0.45, easeOutBack), cards[2]().opacity(1, 0.3));
    })(),
  );
  yield* waitFor(3.0);
  yield* say(bar, label, 'Old funds, real hate groups, and one very lonely vote.');
  yield* waitFor(5.5);

  sfx('whoosh');
  yield* all(
    header().opacity(0, 0.35),
    cards[0]().opacity(0, 0.35),
    cards[1]().opacity(0, 0.35),
    cards[2]().opacity(0, 0.35),
    bar().opacity(0, 0.35),
  );
});
