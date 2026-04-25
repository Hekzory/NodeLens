import { createTheme, type MantineColorsTuple } from '@mantine/core';

// NodeLens cyan — instrument azure, hue ~209°, OKLCH-spaced.
// Index 6 is the keystone (button fill, chart line, focus ring).
const cyan: MantineColorsTuple = [
  '#e7faff',
  '#c7f2ff',
  '#96e4fa',
  '#56d2ed',
  '#00c2de',
  '#00b3cd',
  '#00a2bb',
  '#00889d',
  '#006c7e',
  '#005362',
];

// Brand purple — anchored to logo `#863bff`. Editorial accent only.
// Index 6 is the keystone, 7 is hover, 8 is deepest.
const brand: MantineColorsTuple = [
  '#f5edff',
  '#ece1ff',
  '#d6c1ff',
  '#b89bff',
  '#a070ff',
  '#9354ff',
  '#863bff',
  '#6f24e6',
  '#5a14c2',
  '#48109a',
];

export const theme = createTheme({
  primaryColor: 'cyan',
  primaryShade: 6,
  defaultRadius: 'md',
  cursorType: 'pointer',
  fontFamily:
    'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  fontFamilyMonospace:
    '"JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace',
  headings: {
    fontFamily: 'Inter, sans-serif',
    fontWeight: '600',
    sizes: {
      h1: { fontSize: '34px', lineHeight: '1.3', fontWeight: '600' },
      h2: { fontSize: '26px', lineHeight: '1.35', fontWeight: '600' },
      h3: { fontSize: '22px', lineHeight: '1.4', fontWeight: '600' },
      h4: { fontSize: '18px', lineHeight: '1.45', fontWeight: '600' },
      h5: { fontSize: '16px', lineHeight: '1.5', fontWeight: '600' },
      h6: { fontSize: '14px', lineHeight: '1.5', fontWeight: '600' },
    },
  },
  fontSizes: {
    xs: '12px',
    sm: '14px',
    md: '16px',
    lg: '18px',
    xl: '20px',
  },
  lineHeights: {
    xs: '1.4',
    sm: '1.55',
    md: '1.55',
    lg: '1.55',
    xl: '1.5',
  },
  radius: {
    xs: '2px',
    sm: '4px',
    md: '8px',
    lg: '16px',
    xl: '32px',
  },
  shadows: {
    xs: '0 1px 3px rgba(0, 0, 0, 0.5), 0 1px 2px rgba(0, 0, 0, 0.3)',
    sm: '0 1px 3px rgba(0, 0, 0, 0.5), 0 10px 15px -5px rgba(0, 0, 0, 0.4), 0 7px 7px -5px rgba(0, 0, 0, 0.3)',
    md: '0 1px 3px rgba(0, 0, 0, 0.5), 0 20px 25px -5px rgba(0, 0, 0, 0.4), 0 10px 10px -5px rgba(0, 0, 0, 0.3)',
    lg: '0 1px 3px rgba(0, 0, 0, 0.5), 0 28px 23px -7px rgba(0, 0, 0, 0.4), 0 12px 12px -7px rgba(0, 0, 0, 0.3)',
    xl: '0 1px 3px rgba(0, 0, 0, 0.5), 0 28px 23px -7px rgba(0, 0, 0, 0.4), 0 12px 12px -7px rgba(0, 0, 0, 0.3)',
  },
  colors: {
    cyan,
    brand,
  },
});
