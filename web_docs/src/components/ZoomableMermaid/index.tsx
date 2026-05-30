import React from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import Mermaid from '@theme/Mermaid';
import styles from './styles.module.css';

interface ZoomableMermaidProps {
  value: string;
  title?: string;
}

export default function ZoomableMermaid({ value, title }: ZoomableMermaidProps): JSX.Element {
  return (
    <div className={styles.zoomableContainer}>
      {title && <h3 className={styles.diagramTitle}>{title}</h3>}
      <div className={styles.controls}>
        <span className={styles.controlsLabel}>
          💡 <strong>Tip:</strong> Use mouse wheel to zoom, click and drag to pan, or use the controls below
        </span>
      </div>
      <TransformWrapper
        initialScale={6}
        minScale={0.5}
        maxScale={12}
        centerOnInit={true}
        wheel={{ step: 0.3 }}
        doubleClick={{ disabled: false }}
        panning={{ velocityDisabled: true }}
        limitToBounds={false}
        centerZoomedOut={true}
      >
        {({ zoomIn, zoomOut, resetTransform }) => (
          <>
            <div className={styles.zoomControls}>
              <button 
                onClick={() => zoomIn()} 
                className={styles.zoomButton}
                title="Zoom In"
              >
                🔍+
              </button>
              <button 
                onClick={() => zoomOut()} 
                className={styles.zoomButton}
                title="Zoom Out"
              >
                🔍−
              </button>
              <button 
                onClick={() => resetTransform()} 
                className={styles.zoomButton}
                title="Reset View"
              >
                ⟲ Reset
              </button>
            </div>
            <TransformComponent wrapperClass={styles.transformWrapper} contentClass={styles.transformContent}>
              <div className={styles.mermaidWrapper}>
                <Mermaid value={value} />
              </div>
            </TransformComponent>
          </>
        )}
      </TransformWrapper>
    </div>
  );
}
