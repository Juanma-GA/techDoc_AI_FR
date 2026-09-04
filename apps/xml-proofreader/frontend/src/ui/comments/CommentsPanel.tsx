// Right panel: iterates the declarative tab registry (tabs/registry.tsx).
// To add, rename, or reorder tabs, edit the registry — not this file.
import { useStore } from "../store";
import { TABS } from "./tabs/registry";

export function RightPanel() {
  const rightMode = useStore((s) => s.rightMode);
  const setRight = useStore((s) => s.setRight);

  const ActiveTab = TABS.find((t) => t.id === rightMode)?.component ?? null;

  return (
    <aside className="rightpanel">
      <div className="rp-tabs">
        {TABS.map((tab) => (
          <div
            key={tab.id}
            className={`rp-tab ${rightMode === tab.id ? "active" : ""}`}
            onClick={() => setRight(tab.id)}
          >
            <span className="rp-tab-label">
              {tab.label}
              {tab.badge && <span className="badge"><tab.badge /></span>}
            </span>
          </div>
        ))}
      </div>
      {ActiveTab && <ActiveTab />}
    </aside>
  );
}
