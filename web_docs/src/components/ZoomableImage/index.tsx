import React, {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react';
import {createPortal} from 'react-dom';
import {
  TransformWrapper,
  TransformComponent,
  type ReactZoomPanPinchRef,
} from 'react-zoom-pan-pinch';
import styles from './styles.module.css';

export interface ZoomableImageProps {
  src: string;
  alt: string;
  title?: string;
  /** Max height of the inline preview (CSS). Default 280px. */
  previewMaxHeight?: string;
}

/**
 * Inline preview of a large diagram/PNG with an **Open & zoom** control that
 * opens a fullscreen lightbox (pan + wheel zoom via react-zoom-pan-pinch).
 */
export default function ZoomableImage({
  src,
  alt,
  title,
  previewMaxHeight = '280px',
}: ZoomableImageProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const [portalReady, setPortalReady] = useState(false);
  // Start low so Fit can shrink below 1×; locked to fit scale after first fit.
  const [minScale, setMinScale] = useState(0.05);
  const titleId = useId();
  const label = title || alt;
  const imgRef = useRef<HTMLImageElement | null>(null);
  const apiRef = useRef<ReactZoomPanPinchRef | null>(null);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    setPortalReady(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    setMinScale(0.05);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener('keydown', onKey);
    };
  }, [open, close]);

  const lockMinToFitScale = useCallback((scale: number) => {
    if (!Number.isFinite(scale) || scale <= 0) return;
    // Floor at fit — no zoom-out past the full-diagram view.
    setMinScale(Number(scale.toFixed(4)));
  }, []);

  const fitToView = useCallback(
    (animate = true) => {
      const api = apiRef.current;
      const img = imgRef.current;
      if (!api || !img) return;
      // zoomToElement scales the element into the TransformComponent viewport.
      try {
        api.zoomToElement(
          img,
          undefined,
          animate ? 200 : 0,
          'easeOut',
        );
        const applyFloor = () => {
          const scale = api.state.scale;
          lockMinToFitScale(scale);
        };
        if (animate) {
          window.setTimeout(applyFloor, 220);
        } else {
          applyFloor();
        }
      } catch {
        /* image or stage not ready */
      }
    },
    [lockMinToFitScale],
  );

  const lightbox =
    open && portalReady
      ? createPortal(
          <div
            className={styles.overlay}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
          >
            <TransformWrapper
              initialScale={1}
              minScale={minScale}
              maxScale={8}
              centerOnInit={false}
              // Library default step is 0.015 with smooth=true → step*deltaY per
              // tick (often ~1.5). We want finer grain for diagrams.
              smooth
              wheel={{step: 0.006}}
              doubleClick={{mode: 'toggle', step: 0.5}}
              panning={{velocityDisabled: true}}
              // Default zoomAnimation.size (0.4) lets wheel go minScale-0.4 —
              // that is what produced the tiny corner thumbnail.
              zoomAnimation={{size: 0, disabled: true}}
              disablePadding
              limitToBounds={false}
              onInit={(ref) => {
                apiRef.current = ref;
                requestAnimationFrame(() => fitToView(false));
              }}
            >
              {({zoomIn, zoomOut}) => (
                <>
                  <div className={styles.toolbar}>
                    <p className={styles.toolbarTitle} id={titleId}>
                      {label}
                    </p>
                    <div className={styles.toolbarActions}>
                      <button
                        type="button"
                        className={styles.toolBtn}
                        onClick={() => zoomIn(0.12)}
                      >
                        Zoom in
                      </button>
                      <button
                        type="button"
                        className={styles.toolBtn}
                        onClick={() => zoomOut(0.12)}
                      >
                        Zoom out
                      </button>
                      <button
                        type="button"
                        className={styles.toolBtn}
                        onClick={() => fitToView(true)}
                      >
                        Fit
                      </button>
                      <button
                        type="button"
                        className={styles.toolBtnPrimary}
                        onClick={close}
                      >
                        Close
                      </button>
                    </div>
                  </div>
                  <div className={styles.stage}>
                    <TransformComponent
                      wrapperClass={styles.stageTransform}
                      contentClass={styles.stageContent}
                    >
                      <img
                        ref={imgRef}
                        className={styles.fullImg}
                        src={src}
                        alt={alt}
                        draggable={false}
                        onLoad={() => fitToView(false)}
                      />
                    </TransformComponent>
                  </div>
                  <p className={styles.lightboxHint}>
                    Scroll to zoom · drag to pan · Esc to close
                  </p>
                </>
              )}
            </TransformWrapper>
          </div>,
          document.body,
        )
      : null;

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        {title ? <p className={styles.title}>{title}</p> : <span />}
        <button
          type="button"
          className={styles.openBtn}
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
        >
          Open &amp; zoom
        </button>
      </div>
      <button
        type="button"
        className={styles.previewBtn}
        onClick={() => setOpen(true)}
        aria-label={`Open zoomable view: ${label}`}
      >
        <img
          className={styles.preview}
          src={src}
          alt={alt}
          style={{maxHeight: previewMaxHeight}}
          loading="lazy"
          decoding="async"
        />
        <span className={styles.previewBadge}>Click to zoom</span>
      </button>
      {lightbox}
    </div>
  );
}
