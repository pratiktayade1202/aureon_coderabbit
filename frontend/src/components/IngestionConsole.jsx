// frontend/src/components/ingestion/IngestionConsole.jsx

import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
// FIX: Import specific named functions, NOT "import * as api"
import { uploadIngestionFile, getIngestionStatus } from '../../services/aureonApi'; 
import { useAuth } from '@clerk/clerk-react';

export default function IngestionConsole() {
  const { getToken } = useAuth();
  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState('IDLE'); // IDLE, UPLOADING, PROCESSING, COMPLETED, ERROR

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setStatus('UPLOADING');
    setLogs(prev => [...prev, `🚀 Initializing secure upload: ${file.name}`, `📦 Payload: ${(file.size / 1024).toFixed(1)} KB`]);

    try {
      const token = await getToken();
      
      // FIX: Call the named function directly
      const response = await uploadIngestionFile(file, token);
      
      setLogs(prev => [...prev, "✅ Upload successful", "⏳ Sending to Neural Engine..."]);
      
      // Poll for status if needed, or just show completion
      setStatus('COMPLETED');
      setLogs(prev => [...prev, `✅ Processed: ${response.status}`, ...response.logs]);

    } catch (err) {
      console.error(err);
      setStatus('ERROR');
      setLogs(prev => [...prev, `❌ Critical Failure: ${err.message}`]);
    }
  }, [getToken]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  return (
    <div className="bg-gray-900/50 border border-gray-700 rounded-xl p-6 backdrop-blur-sm">
      <div {...getRootProps()} className={`
        border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
        ${isDragActive ? 'border-blue-500 bg-blue-500/10' : 'border-gray-600 hover:border-gray-500'}
      `}>
        <input {...getInputProps()} />
        <div className="space-y-2">
          <div className="text-4xl">☁️</div>
          <h3 className="text-lg font-medium text-white">Drop financial documents here</h3>
          <p className="text-sm text-gray-400">Supports CSV, Excel, PDF (Ledgers, Trades, Holdings)</p>
        </div>
      </div>

      {/* Log Console */}
      <div className="mt-6 bg-black/80 rounded-lg p-4 font-mono text-sm h-48 overflow-y-auto border border-gray-800">
        <AnimatePresence>
          {logs.map((log, i) => (
            <motion.div 
              key={i}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className={`mb-1 ${log.includes('❌') ? 'text-red-400' : log.includes('✅') ? 'text-green-400' : 'text-gray-300'}`}
            >
              <span className="opacity-50 mr-2">{new Date().toLocaleTimeString().split(' ')[0]}</span>
              {log}
            </motion.div>
          ))}
          {logs.length === 0 && <div className="text-gray-600 italic">System ready... awaiting data stream.</div>}
        </AnimatePresence>
      </div>
    </div>
  );
}