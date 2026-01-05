// src/components/FileUploader.jsx
import React, { useRef, useState, useCallback } from "react";
import {
  UploadCloud,
  FileText,
  FileSpreadsheet,
  FileBox,
  CheckCircle,
  AlertCircle,
  Loader2,
  X,
  Files,
} from "lucide-react";
import { useAuth } from "@clerk/clerk-react";
import { API_BASE_URL } from "../config";

const API_BASE = API_BASE_URL;

/**
 * FileUploader
 * - Drag-and-drop + click
 * - MULTI-FILE SUPPORT: Upload multiple files at once (like ChatGPT/Gemini)
 * - Shows file queue with individual status
 */
const FileUploader = ({ onUploadSuccess }) => {
  const { getToken } = useAuth();
  const [fileQueue, setFileQueue] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragActive, setIsDragActive] = useState(false);
  const [overallStatus, setOverallStatus] = useState(null);
  const fileInputRef = useRef(null);

  // Process a single file
  const processSingleFile = async (file, index, token) => {
    // Update status to uploading
    setFileQueue(prev => prev.map((f, i) =>
      i === index ? { ...f, status: "uploading" } : f
    ));

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/ingestion/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token || "dev-token"}` },
        body: formData,
      });
      const data = await res.json();

      if (data.status === "success") {
        setFileQueue(prev => prev.map((f, i) =>
          i === index ? {
            ...f,
            status: "success",
            message: `${data.rows} rows`
          } : f
        ));
        return { success: true, rows: data.rows };
      } else {
        setFileQueue(prev => prev.map((f, i) =>
          i === index ? {
            ...f,
            status: "error",
            message: data.message || "Failed"
          } : f
        ));
        return { success: false, error: data.message };
      }
    } catch (e) {
      setFileQueue(prev => prev.map((f, i) =>
        i === index ? {
          ...f,
          status: "error",
          message: "Network error"
        } : f
      ));
      return { success: false, error: e.message };
    }
  };

  // Process all files sequentially
  const processAllFiles = async (files) => {
    if (!files || files.length === 0) return;

    setIsUploading(true);
    setOverallStatus(null);

    // Initialize queue with pending status
    const initialQueue = Array.from(files).map(file => ({
      name: file.name,
      size: file.size,
      status: "pending",
      message: null,
      file: file,
    }));
    setFileQueue(initialQueue);

    try {
      const token = await getToken();
      let successCount = 0;
      let totalRows = 0;

      // Process files sequentially
      for (let i = 0; i < files.length; i++) {
        const result = await processSingleFile(files[i], i, token);
        if (result.success) {
          successCount++;
          totalRows += result.rows || 0;
        }
      }

      // Set overall status
      if (successCount === files.length) {
        setOverallStatus({
          type: "success",
          msg: `Successfully uploaded ${successCount} file${successCount > 1 ? 's' : ''} (${totalRows} total rows)`,
        });
        setTimeout(() => onUploadSuccess(), 1500);
      } else if (successCount > 0) {
        setOverallStatus({
          type: "warning",
          msg: `Uploaded ${successCount}/${files.length} files (${totalRows} rows). Some files failed.`,
        });
        setTimeout(() => onUploadSuccess(), 1500);
      } else {
        setOverallStatus({
          type: "error",
          msg: "All uploads failed. Check individual file errors.",
        });
      }
    } catch (e) {
      setOverallStatus({
        type: "error",
        msg: "Upload failed. Check connection.",
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileChange = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      processAllFiles(files);
    }
    // Reset input so same files can be re-selected
    e.target.value = "";
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragActive(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      processAllFiles(files);
    }
  }, []);

  const removeFromQueue = (index) => {
    setFileQueue(prev => prev.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case "uploading":
        return <Loader2 size={14} className="animate-spin text-aureon-blue" />;
      case "success":
        return <CheckCircle size={14} className="text-status-success" />;
      case "error":
        return <AlertCircle size={14} className="text-status-danger" />;
      default:
        return <div className="w-[14px] h-[14px] rounded-full border-2 border-slate-300" />;
    }
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
          onDrop={handleDrop}
          className={`flex flex-col items-center justify-center h-64 border-2 border-dashed rounded-md cursor-pointer transition-colors
            ${isDragActive
              ? "border-aureon-blue bg-slate-50"
              : "border-aureon-border bg-paper-surface hover:bg-slate-50"
            }`}
        >
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="p-3 rounded-sm bg-slate-100 text-ink-muted">
              {isUploading ? (
                <Loader2 size={24} className="animate-spin" />
              ) : (
                <Files size={24} />
              )}
            </div>
            <div>
              <p className="text-sm font-semibold text-ink-strong">
                {isUploading ? "Uploading files..." : "Drop ledger files here"}
              </p>
              <p className="text-[11px] text-ink-muted mt-1">
                Multiple files supported • CSV / XLSX / PDF
              </p>
            </div>
            <button
              type="button"
              disabled={isUploading}
              className="mt-2 px-3 py-1.5 text-[11px] font-semibold rounded-md border border-aureon-border bg-paper-surface hover:bg-slate-100 text-ink-strong disabled:opacity-50"
            >
              Browse Files
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".csv,.xlsx,.xls,.pdf,.zip"
            className="hidden"
            onChange={handleFileChange}
            disabled={isUploading}
          />
        </div>

        {/* File Queue */}
        {fileQueue.length > 0 && (
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-[11px] font-semibold text-ink-muted uppercase tracking-wide">
                Upload Queue ({fileQueue.length} file{fileQueue.length > 1 ? 's' : ''})
              </h4>
              {!isUploading && (
                <button
                  onClick={() => setFileQueue([])}
                  className="text-[10px] text-ink-muted hover:text-ink-strong"
                >
                  Clear all
                </button>
              )}
            </div>
            <div className="max-h-48 overflow-y-auto space-y-1.5">
              {fileQueue.map((file, idx) => (
                <div
                  key={idx}
                  className={`flex items-center gap-3 px-3 py-2 rounded-md border text-[12px]
                    ${file.status === "success" ? "bg-emerald-50 border-emerald-200" : ""}
                    ${file.status === "error" ? "bg-red-50 border-red-200" : ""}
                    ${file.status === "uploading" ? "bg-blue-50 border-blue-200" : ""}
                    ${file.status === "pending" ? "bg-paper-surface border-aureon-border" : ""}
                  `}
                >
                  {getStatusIcon(file.status)}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-ink-strong truncate">{file.name}</p>
                    <p className="text-[10px] text-ink-muted">
                      {formatFileSize(file.size)}
                      {file.message && ` • ${file.message}`}
                    </p>
                  </div>
                  {!isUploading && file.status !== "uploading" && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFromQueue(idx);
                      }}
                      className="p-1 hover:bg-slate-200 rounded"
                    >
                      <X size={12} className="text-ink-muted" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Overall Status */}
        {overallStatus && (
          <div
            className={`mt-3 px-3 py-2 rounded-md flex items-center gap-2 text-[12px] border
              ${overallStatus.type === "success"
                ? "bg-emerald-50 border-emerald-200 text-status-success"
                : overallStatus.type === "warning"
                  ? "bg-amber-50 border-amber-200 text-amber-700"
                  : "bg-red-50 border-red-200 text-status-danger"
              }`}
          >
            {overallStatus.type === "success" ? (
              <CheckCircle size={14} />
            ) : (
              <AlertCircle size={14} />
            )}
            <span>{overallStatus.msg}</span>
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
            <strong>Multi-file upload:</strong> Select or drop multiple files at once.
            They will be processed sequentially with individual status tracking.
          </p>
        </div>
      </div>
    </div>
  );
};

export default FileUploader;
