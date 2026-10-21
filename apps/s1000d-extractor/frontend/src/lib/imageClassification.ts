export function splitImageNames(names: string[]): {
  illustrations: string[];
  pictograms: string[];
} {
  const illustrations: string[] = [];
  const pictograms: string[] = [];

  for (const name of names) {
    if (name.toLowerCase().startsWith("picto_")) pictograms.push(name);
    else illustrations.push(name);
  }

  return { illustrations, pictograms };
}
