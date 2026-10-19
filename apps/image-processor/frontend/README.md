# Image Processor Frontend

The editor uses one authoritative current image for OCR, both brush modes, download,
and per-operation undo. `WorkflowProvider` keeps the active workspace mounted while
navigating between Detection, History, and Settings.
An app-local AppShell layout override prevents the mobile navigation from collapsing
when the editor content is long; shared UI styles remain unchanged.

Startup Excel preferences and complete per-image histories have separate API contracts.
The first restores the workbook and mapping only; the second also restores images,
the selected part, pair edits/selections, OCR results, and the undo stack.
Autosaves are serialized, pending edits are coalesced, and failed saves are visible
and retryable. Browser storage is limited to theme/language preferences.

OCR returns an optional `replacement_font_size` in A4 pixels. It stays with each
analysis revision, including brush edits and saved histories, and is submitted on
later OCR runs so selecting another reference cannot change the common size.
Undoing back to the original clears it. Older histories without the field remain
readable and estimate their font on the next replacement.

Recognized lines can be edited in place after OCR. The selected OCR box is rendered
on the current image without running OCR again; each edit is saved as an undoable
workspace revision. An undo arrow beside the edit icon restores the previous value
for that box; undoing an initial OCR replacement returns it to the recognized text
and marks its box as unmodified without affecting other boxes.

Downloads POST the current image and Excel selection to `/image-processor/export`.
The server supplies the authoritative ICN filename and real A4/300 dpi JPEG;
the brush preview and undo revisions are not re-encoded. Preparation disables
editing, and export errors are shown without starting a download.
**Save** uses the browser's configured download behavior. **Save as** opens the
browser's native JPEG picker; compatible browsers can remember its last folder.
The app does not persist a filesystem path or file handle.

Run `pnpm typecheck`, `pnpm lint`, `pnpm test`, `pnpm build`, and `pnpm test:e2e`
from this directory. Playwright uses a strict isolated local port, `5187`, and
intercepts every API request so smoke tests cannot reach a real backend.

The demo-mode and shared-identity integration contract is documented in the [Demo Mode And Shared Identity guide](../../../docs/standards/demo-mode-integration.md). This frontend README is copied by `scripts/new_poc.sh` and remains available after the generated app README is replaced.