export function latestAssetOfKind<T extends { kind: string }>(
  assets: T[],
  kind: string,
): T | undefined {
  return assets.filter((asset) => asset.kind === kind).at(-1);
}
