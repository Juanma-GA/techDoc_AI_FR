import type { Schemas } from "./api/contracts";
import type { PreliminaryState } from "./preliminaryTypes";

export type DmrlMatchRank = Schemas["DmrlRowOut"]["match_rank"];
export type DmrlTypeIssue = Exclude<NonNullable<Schemas["DmrlRowOut"]["type_issue"]>, "">;
export type DmrlRow = Schemas["DmrlRowOut"];
export type Candidate = Omit<Schemas["CandidateOut"], "score"> & { score?: number };
export type NodeRef = {
  kind: string; target?: string; target_kind?: string; text?: string;
};
export type TreeNode = Omit<Schemas["TreeNodeOut"],
  "text" | "context" | "confidence" | "children" | "candidates" | "refs"> & {
  text: string;
  context: string;
  confidence: number | null;
  children: TreeNode[];
  candidates: Candidate[];
  refs?: NodeRef[] | null;
};
export type WizardStep = Schemas["WizardStateOut"]["step"];
export type PreviewSnippet = Omit<Schemas["PreviewSnippetOut"], "zone"> & { zone?: string };
export type DmPreview = Omit<Schemas["DmPreviewOut"], "head" | "tail"> & {
  head: PreviewSnippet[]; tail: PreviewSnippet[];
};
export type DmValidationStatus = Schemas["DmValidationResultOut"]["status"];
export type DmValidationViolation = Schemas["DmValidationViolationOut"];
export type DmValidationResult = Schemas["DmValidationResultOut"];
export type WizardDm = Omit<Schemas["WizardDmOut"],
  "tree" | "preview" | "xsd_valid" | "xsd_violations" | "brex_violations"> & {
  tree?: TreeNode;
  preview?: DmPreview;
  xsd_valid?: boolean;
  xsd_violations?: DmValidationViolation[];
  brex_violations?: DmValidationViolation[];
};
export type WizardResources = Schemas["WizardResourcesOut"];
export type WizardState = Omit<Schemas["WizardStateOut"],
  "dms" | "preliminary" | "resources" | "dmrl"> & {
  dms: WizardDm[];
  preliminary?: PreliminaryState;
  resources?: WizardResources;
  dmrl?: DmrlRow[];
};
export type Override = { dm_id: string; node_id: string; element: string };
