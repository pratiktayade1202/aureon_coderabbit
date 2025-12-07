// src/components/ingestion/IngestionPanel.jsx
import React, { useState } from "react";
import {
  Upload,
  FileCheck,
  AlertCircle,
  Loader2,
  Database,
} from "lucide-react";

/**
 * IngestionPanel
 * Left rail: upload zone + selected file meta.
 */
const IngestionPanel = ({ onUpload }) => {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) setFile(droppedFile);
  };

  const handleFileInput = (e) => {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  };

  const handleSubmit = async () => {
    if (!file) return;
    setLoading(true);
    await onUpload(file);
    setLoading(false);
  };

  const sizeLabel =
    file && file.size
      ? `${(file.size / 1024).toFixed(1)} KB`
      : "Awaiting file";

  return (
    <div className="border border-aureon-border bg-paper-surface h-full rounded-md flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-aureon-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database size={14} className="text-ink-muted" />
          <div>
            <p className="text-[11px] font-semibold text-ink-strong uppercase tracking-wide">
              File Staging
            </p>
            <p className="text-[10px] text-ink-muted">
              One file at a time. Bulk later.
            </p>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 flex flex-col gap-3 p-4">
        {/* Dropzone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`flex-1 flex items-center justify-center border border-dashed rounded-md p-4 text-center cursor-pointer transition-colors
            ${
              dragging
                ? "border-aureon-blue bg-blue-50/40"
                : "border-aureon-border bg-paper-subtle hover:bg-slate-50"
            }`}
          onClick={() =>
            document.getElementById("hidden-ingestion-file-input")?.click()
          }
        >
          <div>
            <Upload size={20} className="mx-auto mb-2 text-ink-muted" />
            <p className="text-[11px] text-ink-muted">
              Drop CSV/XLSX or click to select
            </p>
            <p className="text-[10px] text-ink-faint mt-1">
              Broker trades, cash ledger, positions, NAV.
            </p>
          </div>
          <input
            id="hidden-ingestion-file-input"
            type="file"
            className="hidden"
            onChange={handleFileInput}
          />
        </div>

        {/* File info */}
        {file ? (
          <div className="px-3 py-2 rounded-md border border-aureon-border bg-paper-subtle flex items-center gap-3">
            <FileCheck size={16} className="text-aureon-blue" />
            <div className="flex-1">
              <p className="text-[11px] text-ink-strong truncate">
                {file.name}
              </p>
              <p className="text-[10px] text-ink-muted">{sizeLabel}</p>
            </div>
          </div>
        ) : (
          <div className="px-3 py-2 rounded-md border border-aureon-border bg-paper-subtle flex items-center gap-2">
            <AlertCircle size={14} className="text-ink-faint" />
            <p className="text-[11px] text-ink-muted">No file selected.</p>
          </div>
        )}

        {/* Button */}
        <button
          disabled={!file || loading}
          onClick={handleSubmit}
          className={`h-9 rounded-md text-[12px] font-semibold flex items-center justify-center gap-2 
            ${
              !file || loading
                ? "bg-slate-200 text-ink-muted cursor-not-allowed"
                : "bg-slate-900 text-white hover:bg-black"
            }`}
        >
          {loading ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              Ingesting…
            </>
          ) : (
            "Start Ingestion"
          )}
        </button>
      </div>
    </div>
  );
};

export default IngestionPanel;
