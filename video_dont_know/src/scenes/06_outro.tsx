import {makeScene2D, Rect, Txt} from '@canvas-commons/2d';
import {all, createRef, easeOutBack, waitFor} from '@canvas-commons/core';
import {MEETING} from '../decision';
import {BODY, COLORS, DISPLAY, makeBackground, sfx} from '../lib';

export default makeScene2D(function* (view) {
  view.add(makeBackground(COLORS.cyan));

  const big = createRef<Txt>();
  const sub = createRef<Txt>();
  const credit = createRef<Rect>();

  view.add(
    <>
      <Txt
        ref={big}
        text={'NOW YOU\nKNOW'}
        y={-300}
        textAlign={'center'}
        fontFamily={DISPLAY}
        fontWeight={900}
        fontSize={180}
        fill={COLORS.yellow}
        opacity={0}
        scale={0}
        rotation={-3}
        shadowColor={COLORS.magenta}
        shadowBlur={28}
        shadowOffset={[8, 8]}
      />
      <Txt
        ref={sub}
        text="…more than most of Phoenix."
        y={20}
        width={940}
        textAlign={'center'}
        textWrap
        fontFamily={BODY}
        fontWeight={700}
        fontSize={56}
        fill={COLORS.white}
        opacity={0}
      />
      <Rect
        ref={credit}
        y={360}
        width={980}
        height={240}
        radius={20}
        fill={COLORS.ink}
        stroke={COLORS.cyan}
        lineWidth={4}
        opacity={0}
        layout
        direction={'column'}
        alignItems={'center'}
        justifyContent={'center'}
        gap={14}
        padding={28}
      >
        <Txt
          text={`${MEETING.body}`}
          fontFamily={BODY}
          fontWeight={800}
          fontSize={40}
          fill={COLORS.white}
        />
        <Txt
          text={`${MEETING.dateLabel} · ${MEETING.agendaItem}`}
          fontFamily={BODY}
          fontWeight={700}
          fontSize={36}
          fill={COLORS.white}
        />
        <Txt
          text={`Frame analysis by Open Navigator · ${MEETING.videoId}`}
          fontFamily={BODY}
          fontWeight={600}
          fontSize={30}
          fill={COLORS.dim}
        />
      </Rect>
    </>,
  );

  sfx('stinger');
  yield* all(big().scale(1, 0.6, easeOutBack), big().opacity(1, 0.4));
  yield* big().rotation(2, 0.12).to(-3, 0.12);
  sfx('applause', -3);
  yield* sub().opacity(1, 0.4);
  yield* credit().opacity(1, 0.5);
  yield* waitFor(5.0);
  yield* all(
    big().opacity(0, 0.6),
    sub().opacity(0, 0.6),
    credit().opacity(0, 0.6),
  );
  yield* waitFor(0.3);
});
