import { api, wizardApi } from "./api";
import i18n from "../i18n";
import type { PageAnchors, PreliminaryState, ReviewAction, SourcePage } from "./preliminaryTypes";

const path = (docId: string) => `/documents/${encodeURIComponent(docId)}/wizard/preliminary`;

export const preliminaryApi = {
  save: (docId: string, revision: number, action: ReviewAction, keepalive = false) =>
    api<PreliminaryState>(path(docId), {
      method: "POST",
      keepalive,
      body: JSON.stringify({ ...action, revision }),
    }),
  read: async (docId: string) => {
    const state = await wizardApi.get(docId);
    if (!state.preliminary) throw new Error(i18n.t("preliminary.unavailable"));
    return state.preliminary;
  },
  pages: (docId: string, dmId: string) =>
    api<SourcePage[]>(`${path(docId)}/${encodeURIComponent(dmId)}/pages`),
  anchors: (docId: string, dmId: string, page: number) =>
    api<PageAnchors>(`${path(docId)}/${encodeURIComponent(dmId)}/page/${page}`),
};
