// src/components/ingestion/IngestionPreviewModal.jsx
import React from "react";
import {
    CheckCircle,
    AlertTriangle,
    ArrowRight,
    FileText,
    ShieldCheck,
    X
} from "lucide-react";

/**
 * IngestionPreviewModal
 * The "Cockpit" for the operator to review the AI's proposal.
 * 
 * Props:
 * - isOpen: bool
 * - onClose: func
 * - contract: obj (from backend)
 * - onApprove: func
 */
const IngestionPreviewModal = ({ isOpen, onClose, contract, onApprove, isApproving }) => {
    if (!isOpen || !contract) return null;

    const mapping = contract.mapping || {};
    const confidence = contract.confidence || { score: 0 };
    const intent = contract.dataset_type || "UNKNOWN";

    // Calculate display color based on confidence
    const getConfidenceColor = (score) => {
        if (score >= 0.9) return "text-emerald-600 bg-emerald-50 border-emerald-200";
        if (score >= 0.7) return "text-amber-600 bg-amber-50 border-amber-200";
        return "text-red-600 bg-red-50 border-red-200";
    };

    const confStyle = getConfidenceColor(confidence.score);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-white w-full max-w-2xl rounded-lg shadow-2xl border border-slate-200 flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50 rounded-t-lg">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-100 text-blue-600 rounded-md">
                            <ShieldCheck size={20} />
                        </div>
                        <div>
                            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Ingestion Contract</h2>
                            <p className="text-xs text-slate-500">Review AI Proposal before signing</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 overflow-y-auto flex-1">

                    {/* Top Stats */}
                    <div className="grid grid-cols-2 gap-4 mb-6">
                        <div className="p-4 rounded-md border border-slate-200 flex flex-col gap-1">
                            <span className="text-xs font-semibold text-slate-400 uppercase">Values Detected As</span>
                            <div className="flex items-center gap-2">
                                <FileText size={18} className="text-slate-600" />
                                <span className="font-bold text-lg text-slate-800">{intent}</span>
                            </div>
                        </div>

                        <div className={`p-4 rounded-md border flex flex-col gap-1 ${confStyle}`}>
                            <span className="text-xs font-semibold opacity-70 uppercase">Confidence Score</span>
                            <div className="flex items-center gap-2">
                                <span className="font-mono font-bold text-2xl">{(confidence.score * 100).toFixed(0)}%</span>
                                {confidence.score < 0.9 && <AlertTriangle size={16} />}
                            </div>
                        </div>
                    </div>

                    {/* Mapping Table */}
                    <div className="mb-4">
                        <h3 className="text-sm font-semibold text-slate-700 mb-3">Schema Mapping</h3>
                        <div className="border border-slate-200 rounded-md overflow-hidden">
                            <table className="w-full text-sm text-left">
                                <thead className="bg-slate-50 text-slate-500 border-b border-slate-200">
                                    <tr>
                                        <th className="px-4 py-2 font-medium">Source Column</th>
                                        <th className="px-4 py-2 font-medium w-8"></th>
                                        <th className="px-4 py-2 font-medium">Target Field</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {Object.entries(mapping).map(([source, target]) => (
                                        <tr key={source} className="hover:bg-slate-50/50">
                                            <td className="px-4 py-2 font-mono text-slate-600">{source}</td>
                                            <td className="px-4 py-2 text-slate-300"><ArrowRight size={14} /></td>
                                            <td className="px-4 py-2 font-mono text-blue-600 font-medium">{target}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Provenance / Disclaimer */}
                    <div className="p-3 bg-slate-50 rounded-md border border-slate-200 text-xs text-slate-500">
                        <p>By approving, you confirm that the schema mapping above is correct. This action will be logged in the audit trail.</p>
                    </div>

                </div>

                {/* Footer */}
                <div className="p-4 border-t border-slate-100 flex justify-end gap-3 bg-slate-50 rounded-b-lg">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
                        disabled={isApproving}
                    >
                        Reject & Cancel
                    </button>
                    <button
                        onClick={onApprove}
                        disabled={isApproving}
                        className="px-5 py-2 text-sm font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-md shadow-sm flex items-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isApproving ? "Signing..." : "Approve & Ingest"}
                        {!isApproving && <CheckCircle size={16} />}
                    </button>
                </div>

            </div>
        </div>
    );
};

export default IngestionPreviewModal;
