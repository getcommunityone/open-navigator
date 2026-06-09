import {makeScene2D, Rect, Txt} from '@canvas-commons/2d';
import {
  all,
  createRef,
  easeOutBack,
  easeOutCubic,
  waitFor,
} from '@canvas-commons/core';
import {MEETING} from '../decision';
import {
  BODY,
  COLORS,
  DISPLAY,
  HostBar,
  makeBackground,
  say,
  sfx,
} from '../lib';

export default makeScene2D(function* (view) {
  view.add(makeBackground(COLORS.cyan));

  const l1 = createRef<Txt>();
  const l2 = createRef<Txt>();
  const sub = createRef<Rect>();
  const footer = createRef<Txt>();
  const bar = createRef<Rect>();
  const label = createRef<Txt>();

  view.add(
    <>
      <Txt
        ref={l1}
        text="YOU DON'T KNOW"
        y={-560}
        fontFamily={DISPLAY}
        fontWeight={900}
        fontSize={80}
        fill={COLORS.white}
        opacity={0}
        scale={0.4}
        letterSpacing={3}
      />
      <Txt
        ref={l2}
        text="PHOENIX"
        y={-360}
        fontFamily={DISPLAY}
        fontWeight={900}
        fontSize={210}
        fill={COLORS.yellow}
        opacity={0}
        scale={0}
        rotation={-4}
        shadowColor={COLORS.magenta}
        shadowBlur={0}
        shadowOffset={[10, 10]}
      />
      <Rect
        ref={sub}
        y={-150}
        width={900}
        height={110}
        radius={16}
        fill={COLORS.magenta}
        rotation={-2}
        opacity={0}
        scale={0.8}
        alignItems={'center'}
        justifyContent={'center'}
      >
        <Txt
          text="THE CITY COUNCIL QUIZ SHOW"
          fontFamily={DISPLAY}
          fontWeight={900}
          fontSize={46}
          fill={COLORS.ink}
          letterSpacing={2}
        />
      </Rect>
      <Txt
        ref={footer}
        text={`${MEETING.body}\n${MEETING.dateLabel}`}
        y={20}
        textAlign={'center'}
        fontFamily={BODY}
        fontWeight={700}
        fontSize={40}
        fill={COLORS.dim}
        opacity={0}
      />
      {HostBar({barRef: bar, labelRef: label})}
    </>,
  );

  yield* all(l1().opacity(1, 0.5), l1().scale(1, 0.5, easeOutBack));
  sfx('stinger');
  yield* all(
    l2().scale(1, 0.6, easeOutBack),
    l2().opacity(1, 0.4),
    l2().shadowBlur(30, 0.6),
  );
  // cheeky wiggle on the logo
  yield* l2().rotation(3, 0.12).to(-2, 0.12).to(0, 0.12);
  sfx('pop');
  yield* all(sub().scale(1, 0.4, easeOutBack), sub().opacity(1, 0.3));
  yield* footer().opacity(1, 0.4);
  yield* waitFor(0.8);

  yield* say(bar, label, "90 seconds. One gloriously messy vote. Let's play.");
  yield* waitFor(4.5);

  sfx('whoosh');
  yield* all(
    l1().opacity(0, 0.4),
    l2().scale(0.6, 0.4, easeOutCubic),
    l2().opacity(0, 0.4),
    sub().opacity(0, 0.3),
    footer().opacity(0, 0.3),
    bar().opacity(0, 0.3),
  );
});
