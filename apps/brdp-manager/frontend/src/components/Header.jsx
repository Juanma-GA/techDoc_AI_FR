import { FileText, Code2, Upload } from 'lucide-react';

/**
 * Page-header action bar for the BRDP Records page (rule #13 `.page-header`
 * convention — no separate app-wide top bar / logo; the brand lives in the
 * sidebar only).
 */
export default function Header({ onChatClick, chatOpen, onOpenGenerateModal, onOpenBREXdocModal, onOpenAIExtractModal, onToggleImport, importOpen }) {
  return (
    <div className="page-header">
      <div>
        <h1>BRDP Records</h1>
        <p>Import, validate, and generate BREX / Schematron from your BRDPs.</p>
      </div>
      <div className="page-header-actions">
        <button onClick={onToggleImport} className={importOpen ? 'btn active' : 'btn secondary'} title="Import / export BRDPs to/from Excel">
          <Upload size={16} />
          Import / Export
        </button>
        <button onClick={() => onOpenAIExtractModal()} className="btn secondary" title="Extract BRDPs from a document">
          AI Extract
        </button>
        <button onClick={() => onOpenBREXdocModal?.()} className="btn secondary" title="Generate BREXdoc">
          <FileText size={16} />
          Generate BREXdoc
        </button>
        <button onClick={onOpenGenerateModal} className="btn primary" title="Generate BREX / Schematron">
          <Code2 size={16} />
          Generate BREX / Schematron
        </button>
        <button onClick={onChatClick} className={chatOpen ? 'btn active' : 'btn secondary'} title={chatOpen ? 'Close BRDP Assistant' : 'Open BRDP Assistant'}>
          ✨ BRDP Assistant
        </button>
      </div>
    </div>
  );
}

