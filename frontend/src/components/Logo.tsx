import type { CSSProperties } from 'react';

type Variant = 'mark' | 'lockup';

type LogoProps = {
  variant?: Variant;
  size?: number;
  style?: CSSProperties;
  className?: string;
};

/**
 * NodeLens logo. The mark is a stepped digital trace (cyan-6) terminating in a
 * brand-purple "now" pip. The lockup pairs the mark with the wordmark.
 *
 * Size on the lockup variant is the height of the mark (the wordmark scales
 * proportionally). Stays legible down to 16px.
 */
export function Logo({ variant = 'mark', size = 24, style, className }: LogoProps) {
  if (variant === 'mark') {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="none"
        strokeLinecap="square"
        strokeLinejoin="miter"
        style={style}
        className={className}
        aria-label="NodeLens"
        role="img"
      >
        <path d="M3 18 H7 V13 H12 V8 H17" stroke="var(--cyan-6)" strokeWidth="2.5" />
        <rect x="16" y="6" width="4" height="4" fill="var(--brand-500)" />
      </svg>
    );
  }

  // Lockup: mark at `size` px, wordmark at ~size * 0.83 px to mirror the
  // 200×40 reference (mark 32, text 20).
  const textSize = Math.round(size * 0.625);
  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: Math.max(6, Math.round(size * 0.25)),
        ...style,
      }}
      aria-label="NodeLens"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="none"
        strokeLinecap="square"
        strokeLinejoin="miter"
        style={{ display: 'block' }}
        role="img"
      >
        <path d="M3 18 H7 V13 H12 V8 H17" stroke="var(--cyan-6)" strokeWidth="2.5" />
        <rect x="16" y="6" width="4" height="4" fill="var(--brand-500)" />
      </svg>
      <span
        style={{
          fontFamily: 'var(--font-sans)',
          fontWeight: 700,
          fontSize: textSize,
          letterSpacing: '-0.02em',
          lineHeight: 1,
          color: 'var(--fg-1)',
        }}
      >
        Node<span style={{ color: 'var(--brand-500)' }}>Lens</span>
      </span>
    </span>
  );
}
