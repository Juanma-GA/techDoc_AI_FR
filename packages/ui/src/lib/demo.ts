export type DemoInputField = {
  id: string;
  label: string;
  initialValue: string;
  multiline?: boolean;
};

export type DemoSampleFile = {
  id: string;
  name: string;
  mediaType: string;
  content: BlobPart;
};

export type DemoScenarioContext = {
  inputs: Readonly<Record<string, string>>;
  files: readonly DemoSampleFile[];
};

export type DemoScenarioResult = string | number | boolean | null | Record<string, unknown> | readonly unknown[];

export type DemoScenario = {
  id: string;
  title: string;
  description: string;
  inputs: readonly DemoInputField[];
  files?: readonly DemoSampleFile[];
  run: (context: DemoScenarioContext) => DemoScenarioResult;
};

export function createDemoFile(sample: DemoSampleFile): File {
  return new File([sample.content], sample.name, { type: sample.mediaType });
}