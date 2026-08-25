import type { ComponentType } from "react";
import type { RightMode } from "../../store";
import { CommentsTab, CommentsTabBadge } from "./CommentsTab";
import { IssuesTab, IssuesTabBadge } from "./IssuesTab";
import { XmlSourceTab } from "./XmlSourceTab";
import { GraderPanel } from "../../grader/GraderPanel";
import { ChatPanel } from "../../chat/ChatPanel";

export type TabDef = {
  id: RightMode;
  label: string;
  badge?: ComponentType;
  component: ComponentType;
};

export const TABS: TabDef[] = [
  { id: "comments",    label: "Comments",       badge: CommentsTabBadge, component: CommentsTab },
  { id: "issues",      label: "Issues",         badge: IssuesTabBadge,   component: IssuesTab },
  { id: "chat",        label: "AI Chat",                                 component: ChatPanel },
  { id: "proofreader", label: "AI Proofreader",                          component: GraderPanel },
  { id: "xml",         label: "XML source",                              component: XmlSourceTab },
];
