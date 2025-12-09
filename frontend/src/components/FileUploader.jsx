// src/components/FileUploader.jsx
import React, { useRef, useState } from "react";
import {
  UploadCloud,
  FileText,
  FileSpreadsheet,
  FileBox,
  CheckCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { useAuth } from "@clerk/clerk-react";
import { API_BASE_URL } from "../config";

const API_BASE = API_BASE_URL;

/**
 * FileUploader
 * - Drag-and-drop + click
 * - Cold, structured, no fluff
 */
const FileUploader = ({ onUploadSuccess }) => {
  const { getToken } = useAuth();
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef(null);

  const processUpload = async (file) => {
    if (!file) return;
    setIsUploading(true);
    setUploadStatus(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/ingestion/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token || "dev-token"}` },
        body: formData,
      });
      const data = await res.json();

      if (data.status === "success") {
        setUploadStatus({
          type: "success",
          msg: `Ingested ${data.rows} rows from ${file.name}`,
        });
        setTimeout(() => onUploadSuccess(), 1200);
      } else {
        setUploadStatus({ type: "error", msg: data.message });
      }
    } catch (e) {
      setUploadStatus({
        type: "error",
        msg: "Upload failed. Check connection.",
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) processUpload(file);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Dropzone */}
      <div className="lg:col-span-2">
        <div
          onClick={() => !isUploading && fileInputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragActive(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            setIsDragActive(false);
          }}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragActive(false);
            processUpload(e.dataTransfer.files[0]);
          }}
          className={`flex flex-col items-center justify-center h-64 border-2 border-dashed rounded-md cursor-pointer transition-colors
            ${
              isDragActive
                ? "border-aureon-blue bg-slate-50"
                : "border-aureon-border bg-paper-surface hover:bg-slate-50"
            }`}
        >
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="p-3 rounded-sm bg-slate-100 text-ink-muted">
              {isUploading ? (
                <Loader2 size={24} className="animate-spin" />
              ) : (
                <UploadCloud size={24} />
              )}
            </div>
            <div>
              <p className="text-sm font-semibold text-ink-strong">
                {isUploading ? "Ingesting file..." : "Drop ledger files here"}
              </p>
              <p className="text-[11px] text-ink-muted mt-1">
                Bank, broker, or custodian exports. CSV / XLSX / PDF.
              </p>
            </div>
            <button
              type="button"
              className="mt-2 px-3 py-1.5 text-[11px] font-semibold rounded-md border border-aureon-border bg-paper-surface hover:bg-slate-100 text-ink-strong"
            >
              Browse Files
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={handleFileChange}
            disabled={isUploading}
          />
        </div>

        {/* Status */}
        {uploadStatus && (
          <div
            className={`mt-3 px-3 py-2 rounded-md flex items-center gap-2 text-[12px] border
              ${
                uploadStatus.type === "success"
                  ? "bg-emerald-50 border-emerald-200 text-status-success"
                  : "bg-red-50 border-red-200 text-status-danger"
              }`}
          >
            {uploadStatus.type === "success" ? (
              <CheckCircle size={14} />
            ) : (
              <AlertCircle size={14} />
            )}
            <span>{uploadStatus.msg}</span>
          </div>
        )}
      </div>

      {/* Right meta column */}
      <div className="space-y-3">
        <h3 className="text-[11px] font-semibold text-ink-muted uppercase tracking-wide">
          Supported Sources
        </h3>
        {[
          { label: "Bank Ledgers", detail: "CSV / MT940", icon: FileText },
          { label: "Broker Contracts", detail: "PDF / HTML", icon: FileBox },
          {
            label: "Custody Holdings",
            detail: "XLSX / CAS",
            icon: FileSpreadsheet,
          },
        ].map((item, idx) => {
          const Icon = item.icon;
          return (
            <div
              key={idx}
              className="flex items-center gap-3 bg-paper-surface border border-aureon-border rounded-md px-3 py-2"
            >
              <div className="p-1.5 rounded-sm bg-slate-100 text-ink-muted">
                <Icon size={16} />
              </div>
              <div className="flex flex-col">
                <span className="text-[12px] font-semibold text-ink-strong">
                  {item.label}
                </span>
                <span className="text-[11px] font-mono text-ink-faint">
                  {item.detail}
                </span>
              </div>
            </div>
          );
        })}

        <div className="mt-4 bg-paper-cream border border-aureon-border rounded-md px-3 py-2">
          <p className="text-[11px] text-ink-muted">
            Files are parsed via the Aureon AI ingestion layer. Avoid password
            protected PDFs for now.
          </p>
        </div>
      </div>
    </div>
  );
};

export default FileUploader;
