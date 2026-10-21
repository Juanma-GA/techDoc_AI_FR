import { createContext, useContext, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useImageReplace } from "./useImageReplace";

const WorkflowContext = createContext<ReturnType<typeof useImageReplace> | null>(null);

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const workflow = useImageReplace(t);
  return <WorkflowContext.Provider value={workflow}>{children}</WorkflowContext.Provider>;
}

export function useWorkflow() {
  const workflow = useContext(WorkflowContext);
  if (!workflow) throw new Error("The image workflow requires WorkflowProvider.");
  return workflow;
}
