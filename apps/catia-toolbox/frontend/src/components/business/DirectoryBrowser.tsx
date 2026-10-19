import { FilePicker } from "../FilePicker";
import type { BrowseScope } from "../../lib/api";

export type DirectoryBrowserProps = {
  scope?: BrowseScope;
  /** Chemins absolus coches (controle par le parent). */
  selection: Set<string>;
  onSelectionChange: (next: Set<string>) => void;
};

/**
 * Navigateur d'arborescence OneDrive (lazy, un niveau par appel). Cases a cocher
 * sur fichiers ET dossiers. Skin "preview-skin" (classes .item-list / .checkbox).
 */
export function DirectoryBrowser({ scope = "input", selection, onSelectionChange }: DirectoryBrowserProps) {
  return (
    <FilePicker
      mode="multi"
      scope={scope}
      exts={[]}
      value={Array.from(selection)}
      onChange={(paths) => onSelectionChange(new Set(paths))}
      allowRecursive={false}
    />
  );
}
