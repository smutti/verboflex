const PRODUCT_PALETTE = [
  { accent: "#0f766e", soft: "#ccfbf1", ink: "#134e4a" },
  { accent: "#1d4ed8", soft: "#dbeafe", ink: "#1e3a8a" },
  { accent: "#7e22ce", soft: "#f3e8ff", ink: "#581c87" },
  { accent: "#be123c", soft: "#ffe4e6", ink: "#881337" },
  { accent: "#b45309", soft: "#fef3c7", ink: "#78350f" },
  { accent: "#047857", soft: "#d1fae5", ink: "#064e3b" },
  { accent: "#4338ca", soft: "#e0e7ff", ink: "#312e81" },
  { accent: "#c2410c", soft: "#ffedd5", ink: "#7c2d12" },
] as const;

function stableHash(value: string) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function productInitials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "PR";
  return words
    .slice(0, 2)
    .map((word) => Array.from(word)[0]?.toLocaleUpperCase() ?? "")
    .join("");
}

export function productIdentity(productId: string, productName: string) {
  const palette =
    PRODUCT_PALETTE[stableHash(productId) % PRODUCT_PALETTE.length];
  return { ...palette, initials: productInitials(productName) };
}
