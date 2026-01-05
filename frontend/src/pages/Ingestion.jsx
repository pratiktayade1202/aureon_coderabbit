// src/pages/Ingestion.jsx
import React, { useState } from "react";
import { useAureonApi } from "../hooks/useAureonApi";

// Components
import IngestionUtilityBar from "../components/ingestion/IngestionUtilityBar";
import IngestionPanel from "../components/ingestion/IngestionPanel";
import IngestionConsole from "../components/ingestion/IngestionConsole";
import IngestionHistoryTable from "../components/ingestion/IngestionHistoryTable";
import IngestionPreviewModal from "../components/ingestion/IngestionPreviewModal";

const Ingestion = ({ onUploadComplete }) => {
  const api = useAureonApi();
  const [consoleLogs, setConsoleLogs] = useState([]);
  const [showPreview, setShowPreview] = useState(false);
  const [contractData, setContractData] = useState(null);
  const [isApproving, setIsApproving] = useState(false);

  // Helper to add timestamped logs
  const addLog = (msg) => {
    const time = new Date().toLocaleTimeString('en-US', {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
    setConsoleLogs((prev) => [...prev, `[${time}] ${msg}`]);
  };

  const handleUpload = async (file) => {
    addLog(`🚀 [GLASS-BOX V3] Initializing upload for: ${file.name}`);

    try {
      const formData = new FormData();
      formData.append("file", file);

      addLog("📡 Transmitting to Glass-Box Engine...");

      // 1. START SESSION
      const sessionRes = await api.startIngestionSession(formData);

      if (sessionRes.status === "DRAFT") {
        addLog(`✅ File Analyzed. Session ID: ${sessionRes.session_id}`);
        addLog("📋 Fetching contract proposal...");

        // 2. GET PREVIEW
        const statusRes = await api.getSessionStatus(sessionRes.session_id);

        if (statusRes.contract) {
          setContractData(statusRes.contract);
          setShowPreview(true);
          addLog("⚖️  Presents Contract for Approval. Waiting for human sign-off...");
        } else {
          addLog("⚠️ Analysis incomplete: No contract generated. Is the file empty or encrypted?");
        }
      }

    } catch (error) {
      const errMsg = error.message || "Unknown Error";
      addLog(`❌ Upload Failed: ${errMsg}`);
    }
  };

  const handleApprove = async () => {
    if (!contractData) return;
    setIsApproving(true);
    addLog("✍️  Signing Ingestion Contract...");

    try {
      const res = await api.approveContract(contractData.id, contractData.mapping);

      if (res.status === "success") {
        addLog(`✅ Contract Signed! Execution Queued (ID: ${res.execution_id})`);
        setShowPreview(false);

        addLog("🔄 Redirecting to Dashboard in 2 seconds...");
        setTimeout(() => {
          if (onUploadComplete) onUploadComplete();
        }, 2000);
      }
    } catch (e) {
      addLog(`❌ Signing Failed: ${e.message}`);
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div className="p-6 max-w-[1600px] mx-auto h-screen flex flex-col">
      <IngestionUtilityBar />

      <div className="flex-1 min-h-0 grid grid-cols-12 gap-6 mb-6">
        {/* Left Panel: Upload Actions */}
        <div className="col-span-3">
          <IngestionPanel onUpload={handleUpload} />
        </div>

        {/* Right Panel: Live Console Logs */}
        <div className="col-span-9 h-full min-h-0 overflow-hidden">
          <IngestionConsole realLogs={consoleLogs} />
        </div>
      </div>

      {/* Bottom Panel: History */}
      <div className="flex-shrink-0">
        <IngestionHistoryTable />
      </div>

      <IngestionPreviewModal
        isOpen={showPreview}
        contract={contractData}
        onClose={() => setShowPreview(false)}
        onApprove={handleApprove}
        isApproving={isApproving}
      />
    </div>
  );
};

export default Ingestion;