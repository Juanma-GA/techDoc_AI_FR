import { useState, useRef } from 'react';
import { generateTemplate, importFromExcel, exportToExcel, exportToCSV } from '../utils/excelUtils';

/**
 * Import / export BRDPs to/from Excel — lives on the BRDP Records page (not
 * Données), since it's a working-with-the-list concern, not data
 * housekeeping. Uses the shared `.card`/`.btn`/`.label` shell classes.
 * @param {Object} props
 * @param {Array} props.brdps - Current BRDP records
 * @param {Function} props.onSetBrdps - Callback to update BRDPs
 * @param {Function} props.showToast - Callback to show toast notifications
 */
export default function ImportSection({ brdps, onSetBrdps, showToast }) {
  const [importedRows, setImportedRows] = useState([]);
  const [importErrors, setImportErrors] = useState([]);
  const [importMode, setImportMode] = useState(null);
  const fileInputRef = useRef(null);

  const handleDownloadTemplate = () => {
    const blob = new Blob([generateTemplate()], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'brdp-template.xlsx';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const handleFileSelect = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setImportErrors([]);
    setImportedRows([]);

    const { rows, errors } = await importFromExcel(file);

    if (errors.length > 0) {
      setImportErrors(errors);
      setImportedRows([]);
      setImportMode(null);
    } else if (rows.length === 0) {
      setImportErrors(['No valid data found in file']);
      setImportMode(null);
    } else {
      setImportedRows(rows);
      setImportMode('preview');
      setImportErrors([]);
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleReplaceAll = () => {
    onSetBrdps(importedRows);
    setImportedRows([]);
    setImportMode(null);
    if (showToast) {
      showToast(`${importedRows.length} BRDPs imported successfully`, 'success');
    }
  };

  const handleMerge = () => {
    const existingIds = new Set(brdps.map((b) => b.id));
    const newRows = importedRows.filter((row) => !existingIds.has(row.id));
    onSetBrdps([...brdps, ...newRows]);
    setImportedRows([]);
    setImportMode(null);
    if (showToast) {
      showToast(`${newRows.length} new BRDPs imported successfully`, 'success');
    }
  };

  const handleCancelImport = () => {
    setImportedRows([]);
    setImportMode(null);
    setImportErrors([]);
  };

  const handleExportExcel = () => {
    exportToExcel(brdps);
    if (showToast) showToast('File downloaded successfully', 'success');
  };

  const handleExportCSV = () => {
    exportToCSV(brdps);
    if (showToast) showToast('File downloaded successfully', 'success');
  };

  return (
    <div className="card">
      <h2 className="card-title">Import / Export Excel</h2>

      <div className="form">
        <div>
          <div className="label">Template</div>
          <div className="row">
            <button onClick={handleDownloadTemplate} className="btn secondary">
              Download Excel template (.xlsx)
            </button>
          </div>
        </div>

        <div>
          <div className="label">Import BRDPs from Excel</div>
          {importMode === null && (
            <>
              <div className="row">
                <label className="btn secondary" style={{ cursor: 'pointer' }}>
                  Choose Excel file
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".xlsx,.xls"
                    onChange={handleFileSelect}
                    hidden
                  />
                </label>
              </div>
              <p style={{ color: 'var(--fg-dim)', fontSize: '0.8rem', margin: '4px 0 0' }}>
                Select an Excel file created from the template
              </p>
            </>
          )}

          {importErrors.length > 0 && (
            <div className="error">
              Import errors:
              <ul style={{ margin: '4px 0 0', paddingLeft: '18px' }}>
                {importErrors.map((error, idx) => (
                  <li key={idx}>{error}</li>
                ))}
              </ul>
            </div>
          )}

          {importMode === 'preview' && importedRows.length > 0 && (
            <div className="success">
              {importedRows.length} rows found
              <div className="row" style={{ marginTop: 8 }}>
                <button onClick={handleReplaceAll} className="btn primary">
                  Replace all BRDPs
                </button>
                <button onClick={handleMerge} className="btn secondary">
                  Merge
                </button>
                <button onClick={handleCancelImport} className="btn ghost">
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        <div>
          <div className="label">Export current BRDPs</div>
          <div className="row">
            <button onClick={handleExportExcel} className="btn secondary">
              Export to Excel (.xlsx)
            </button>
            <button onClick={handleExportCSV} className="btn secondary">
              Export to CSV
            </button>
          </div>
          <p style={{ color: 'var(--fg-dim)', fontSize: '0.8rem', margin: '4px 0 0' }}>
            {brdps.length} BRDP record{brdps.length !== 1 ? 's' : ''} available for export
          </p>
        </div>
      </div>
    </div>
  );
}
