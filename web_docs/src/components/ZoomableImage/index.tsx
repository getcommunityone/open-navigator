import React, {useCallback, useEffect, useId, useState} from 'react';
import {TransformWrapper, TransformComponent} from 'react-zoom-pan-pinch';
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
  const titleId = useId();
  const label = title || alt;

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
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
        onClick={() => setOpen(true)}
        style={{display: 'block', width: '100%', padding: 0, border: 0, background: 'none'}}
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
      </button>
      <p className={styles.hint}>Preview — click image or Open &amp; zoom to pan and zoom.</p>

      {open ? (
        <div
          className={styles.overlay}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
        >
          <TransformWrapper
            initialScale={1}
            minScale={0.25}
            maxScale={8}
            centerOnInit
            wheel={{step: 0.15}}
            doubleClick={{mode: 'zoomIn', step: 0.4}}
            panning={{velocityDisabled: true}}
            limitToBounds={false}
          >
            {({zoomIn, zoomOut, resetTransform}) => (
              <div className={styles.lightboxInner}>
                <div className={styles.toolbar}>
                  <p className={styles.toolbarTitle} id={titleId}>
                    {label}
                  </p>
                  <div className={styles.toolbarActions}>
                    <button
                      type="button"
                      className={styles.toolBtn}
                      onClick={() => zoomIn()}
                      title="Zoom in"
                    >
                      +
                    </button>
                    <button
                      type="button"
                      className={styles.toolBtn}
                      onClick={() => zoomOut()}
                      title="Zoom out"
                    >
                      −
                    </button>
                    <button
                      type="button"
                      className={styles.toolBtn}
                      onClick={() => resetTransform()}
                      title="Reset"
                    >
                      Reset
                    </button>
                    <button
                      type="button"
                      className={styles.toolBtn}
                      onClick={close}
                      title="Close (Esc)"
                    >
                      Close
                    </button>
                  </div>
                </div>
                <div className={styles.stage}>
                  <TransformComponent
                    wrapperClass={styles.stageTransform}
                    contentClass={styles.stageTransform}
                  >
                    <img className={styles.fullImg} src={src} alt={alt} draggable={false} />
                  </TransformComponent>
                </div>
              </div>
            )}
          </TransformWrapper>
        </div>
      ) : null}
    </div>
  );
}
