import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/clerk-react"; // Import Clerk Auth
import { useAureonApi } from "../hooks/useAureonApi";

// Components
import IngestionUtilityBar from "../components/ingestion/IngestionUtilityBar";
import IngestionPanel from "../components/ingestion/IngestionPanel";
import IngestionConsole from "../components/ingestion/IngestionConsole";
import IngestionHistoryTable from "../components/ingestion/IngestionHistoryTable";

const Ingestion = ({ onUploadComplete }) => {
  const { getToken } = useAuth();
  const api = useAureonApi();
  
  // State for Job Tracking
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null); // PENDING, RUNNING, COMPLETED, FAILED
  const [consoleLogs, setConsoleLogs] = useState(["System Ready. Awaiting data..."]);

  // 1. Handle the Initial Upload
  const handleUpload = async (file) => {
    try {
      // Reset UI state
      setConsoleLogs([
        `🚀 Initializing secure upload: ${file.name}`,
        `📦 Payload: ${(file.size / 1024).toFixed(1)} KB`,
        `⏳ Sending to Neural Engine...`
      ]);
      setStatus("STARTING");

      const token = await getToken();
      const formData = new FormData();
      formData.append("file", file);

      // Call API (Ensure your useAureonApi hook or this method accepts the token if needed)
      // If your useAureonApi already handles headers automatically, you might not need to pass 'token'
      const response = await api.uploadIngestionFile(formData, token);

      setJobId(response.job_id);
      setStatus(response.status);
      
      // Update logs with immediate feedback from server
      if (response.logs && response.logs.length > 0) {
        setConsoleLogs(prev => [...prev, ...response.logs]);
      }

    } catch (error) {
      console.error("Upload failed", error);
      setStatus("FAILED");
      setConsoleLogs(prev => [...prev, `❌ Critical Failure: ${error.message}`]);
    }
  };

  // 2. Poll for Status & Logs
  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;

    const poll = async () => {
      try {
        const token = await getToken();

        // Fetch Status and Logs in parallel
        const [statusRes, logsRes] = await Promise.all([
          api.getIngestionStatus(jobId, token),
          api.getIngestionLogs(jobId, token)
        ]);

        if (cancelled) return;

        // Update Logs (Appending new logs or replacing - depending on backend log strategy)
        // Here assuming backend returns full log history or we just show what we get
        if (logsRes.logs && logsRes.logs.length > 0) {
           // We map them to ensure formatting
           setConsoleLogs(logsRes.logs.map(l => `> ${l}`));
        }

        setStatus(statusRes.status);

        // 3. Handle Completion
        if (statusRes.status === "COMPLETED") {
          setConsoleLogs(prev => [...prev, `✅ Ingestion Successful.`]);
          
          // Trigger the Cinematic Redirect
          setTimeout(() => {
            setConsoleLogs(prev => [...prev, `✨ Process Complete. Redirecting to Dashboard...`]);
            setTimeout(() => {
              if (onUploadComplete) onUploadComplete();
            }, 1500);
          }, 1000);
          
          return; // Stop polling
        }

        // Handle Failure
        if (statusRes.status === "FAILED") {
           setConsoleLogs(prev => [...prev, `❌ Processing Failed.`]);
           return; // Stop polling
        }

        // Continue polling if RUNNING or PENDING
        setTimeout(poll, 1500);

      } catch (err) {
        console.error("Polling error", err);
        if (!cancelled) {
          setConsoleLogs(prev => [...prev, `⚠️ Connection fluctuation: ${err.message}`]);
          // Retry logic could go here, or just keep polling
          setTimeout(poll, 3000); 
        }
      }
    };

    poll();

    return () => { cancelled = true; };
  }, [jobId, getToken, api, onUploadComplete]);

  return (
    <div className="flex flex-col h-full">
      <IngestionUtilityBar />

      <div className="grid grid-cols-1 lg:grid-cols-[360px_minmax(0,1fr)] gap-4 flex-1 min-h-[420px]">
        {/* Pass isUploading logic based on status if needed, or just the handler */}
        <IngestionPanel onUpload={handleUpload} isUploading={status === 'STARTING' || status === 'RUNNING'} />
        
        {/* Pass the real logs from the server */}
        <IngestionConsole realLogs={consoleLogs} status={status} />
      </div>

      <IngestionHistoryTable />
    </div>
  );
};

export default Ingestion;