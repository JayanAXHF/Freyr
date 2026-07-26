export const inr = (v: number, digits = 0): string =>
  `₹${v.toLocaleString('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;

export const num = (v: number, digits = 1): string =>
  v.toLocaleString('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

export const pct = (fraction: number, digits = 0): string =>
  `${(fraction * 100).toFixed(digits)}%`;
