// src/pages/Ingestion.jsx
import React, { useState } from "react";
import { useAureonApi } from "../hooks/useAureonApi";

// Components
import IngestionUtilityBar from "../components/ingestion/IngestionUtilityBar";
import IngestionPanel from "../components/ingestion/IngestionPanel";
import IngestionConsole from "../components/ingestion/IngestionConsole";
import IngestionHistoryTable from "../components/ingestion/IngestionHistoryTable";

const Ingestion = ({ onUploadComplete }) => {
  const api = useAureonApi();
  const [consoleLogs, setConsoleLogs] = useState([]);

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
    addLog(`🚀 Initializing upload for: ${file.name}`);
    
    try {
      const formData = new FormData();
      formData.append("file", file);

      addLog("📡 Transmitting payload to Aureon Core...");
      
      // FIXED: Using the method from the corrected hook (Synchronous call)
      const response = await api.uploadIngestionFile(formData);

      addLog(`✅ Upload Complete. Status: ${response.status}`);
      
      // Display logs returned by the backend immediately
      if (response.logs && Array.isArray(response.logs)) {
        response.logs.forEach(l => addLog(`> ${l}`));
      }
      
      // Auto-navigate to dashboard after successful upload
      if (response.status === "success" || response.status === "Completed") {
        addLog("🔄 Redirecting to Dashboard in 2 seconds...");
        setTimeout(() => {
          if (onUploadComplete) {
            onUploadComplete();
          }
        }, 2000);
      }
      
    } catch (error) {
      const errMsg = error.message || "Unknown Error";
      addLog(`❌ Upload Failed: ${errMsg}`);
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
    </div>
  );
};

export default Ingestion;