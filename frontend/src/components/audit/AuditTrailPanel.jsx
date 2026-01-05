// src/components/audit/AuditTrailPanel.jsx
/**
 * Immutable Audit Trail Panel (v2.1)
 * 
 * Features:
 * - Hash chain integrity verification
 * - Searchable/filterable event log
 * - Export to CSV
 * - Visual hash status indicator
 */
import React, { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    Shield, ShieldCheck, ShieldAlert,
    Search, Download, RefreshCw,
    CheckCircle2, AlertTriangle, Clock,
    ChevronDown, ChevronRight, Hash
} from "lucide-react";
import { useAuth } from "@clerk/clerk-react";
import { API_BASE_URL } from "../../config";

const AuditTrailPanel = () => {
    const { getToken } = useAuth();
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [verifying, setVerifying] = useState(false);
    const [verificationResult, setVerificationResult] = useState(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [filterType, setFilterType] = useState("ALL");
    const [expandedEvent, setExpandedEvent] = useState(null);

    // Fetch audit events
    const fetchEvents = useCallback(async () => {
        setLoading(true);
        try {
            const token = await getToken();
            const res = await fetch(`${API_BASE_URL}/recon/audit-events`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setEvents(Array.isArray(data.events) ? data.events : []);
            }
        } catch (err) {
            console.error("Failed to fetch audit events:", err);
        } finally {
            setLoading(false);
        }
    }, [getToken]);

    // Verify hash chain integrity
    const verifyChain = async () => {
        setVerifying(true);
        try {
            const token = await getToken();
            const res = await fetch(`${API_BASE_URL}/recon/audit-verify`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const result = await res.json();
                setVerificationResult(result);
            }
        } catch (err) {
            setVerificationResult({ valid: false, errors: [err.message] });
        } finally {
            setVerifying(false);
        }
    };

    // Export to CSV
    const exportCSV = async () => {
        try {
            const token = await getToken();
            // TODO: Create /recon/audit-events/export endpoint for consistency
            // Currently exports proposals as audit panel workaround
            const res = await fetch(`${API_BASE_URL}/recon/proposals/export?format=csv`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `audit_export_${new Date().toISOString().split('T')[0]}.csv`;
            a.click();
        } catch (err) {
            console.error("Export failed:", err);
        }
    };

    useEffect(() => {
        fetchEvents();
    }, [fetchEvents]);

    // Filter events
    const filteredEvents = events.filter((e) => {
        const matchesSearch =
            searchQuery === "" ||
            e.event_type?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            e.entity_type?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            e.actor?.toLowerCase().includes(searchQuery.toLowerCase());

        const matchesFilter =
            filterType === "ALL" ||
            e.event_type?.includes(filterType);

        return matchesSearch && matchesFilter;
    });

    const eventTypes = ["ALL", "PROPOSAL", "RUN", "BREAK", "MANUAL"];

    return (
        <div className="h-full flex flex-col bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 flex items-center justify-center rounded-lg bg-slate-900 text-white">
                            <Shield size={18} />
                        </div>
                        <div>
                            <h2 className="text-sm font-semibold text-slate-900">Immutable Audit Trail</h2>
                            <p className="text-[10px] text-slate-500">Hash-chained event log • Tamper-evident</p>
                        </div>
                    </div>

                    {/* Verification Status */}
                    <div className="flex items-center gap-2">
                        {verificationResult && (
                            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium ${verificationResult.valid
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : "bg-red-50 text-red-700 border border-red-200"
                                }`}>
                                {verificationResult.valid ? (
                                    <>
                                        <ShieldCheck size={12} />
                                        <span>Chain Verified ({verificationResult.events_verified} events)</span>
                                    </>
                                ) : (
                                    <>
                                        <ShieldAlert size={12} />
                                        <span>Integrity Error</span>
                                    </>
                                )}
                            </div>
                        )}

                        <button
                            onClick={verifyChain}
                            disabled={verifying}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg border border-slate-200 transition-colors"
                        >
                            <RefreshCw size={12} className={verifying ? "animate-spin" : ""} />
                            {verifying ? "Verifying..." : "Verify Chain"}
                        </button>

                        <button
                            onClick={exportCSV}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium bg-slate-900 hover:bg-slate-800 text-white rounded-lg transition-colors"
                        >
                            <Download size={12} />
                            Export
                        </button>
                    </div>
                </div>
            </div>

            {/* Filters */}
            <div className="px-4 py-2 border-b border-slate-100 bg-slate-50 flex items-center gap-3">
                <div className="relative flex-1 max-w-xs">
                    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search events..."
                        className="w-full pl-9 pr-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-200"
                    />
                </div>

                <div className="flex gap-1">
                    {eventTypes.map((type) => (
                        <button
                            key={type}
                            onClick={() => setFilterType(type)}
                            className={`px-2.5 py-1 text-[10px] font-medium rounded-md transition-all ${filterType === type
                                ? "bg-slate-900 text-white"
                                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
                                }`}
                        >
                            {type}
                        </button>
                    ))}
                </div>
            </div>

            {/* Event List */}
            <div className="flex-1 overflow-y-auto px-4 py-3">
                {loading ? (
                    <div className="flex items-center justify-center h-32 text-slate-400 text-xs">
                        <RefreshCw size={16} className="animate-spin mr-2" />
                        Loading audit trail...
                    </div>
                ) : filteredEvents.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-32 text-slate-400">
                        <Search size={24} className="mb-2 opacity-50" />
                        <span className="text-xs">No events found</span>
                    </div>
                ) : (
                    <div className="space-y-2">
                        {filteredEvents.map((event, idx) => (
                            <AuditEventRow
                                key={event.id || idx}
                                event={event}
                                isExpanded={expandedEvent === event.id}
                                onToggle={() => setExpandedEvent(expandedEvent === event.id ? null : event.id)}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* Footer - Safety Disclosure */}
            <div className="px-4 py-2 border-t border-slate-200 bg-amber-50">
                <p className="text-[10px] text-amber-700 leading-relaxed">
                    <strong>Audit Disclosure:</strong> This log is append-only with SHA256 hash chain.
                    Each event's integrity is verifiable. Aureon is assistive tooling, not a system of record.
                </p>
            </div>
        </div>
    );
};

// Individual Audit Event Row
const AuditEventRow = ({ event, isExpanded, onToggle }) => {
    const getEventIcon = (type) => {
        if (type?.includes("APPROVED")) return <CheckCircle2 size={14} className="text-emerald-500" />;
        if (type?.includes("REJECTED")) return <AlertTriangle size={14} className="text-red-500" />;
        if (type?.includes("CREATED")) return <Clock size={14} className="text-blue-500" />;
        return <Hash size={14} className="text-slate-400" />;
    };

    const formatTimestamp = (ts) => {
        if (!ts) return "";
        try {
            return new Date(ts).toLocaleString();
        } catch {
            return ts;
        }
    };

    return (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden hover:shadow-sm transition-shadow">
            <button
                onClick={onToggle}
                className="w-full px-3 py-2.5 flex items-center gap-3 text-left"
            >
                <div className="w-7 h-7 flex items-center justify-center rounded-full bg-slate-100">
                    {getEventIcon(event.event_type)}
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-slate-800">{event.event_type}</span>
                        <span className="px-1.5 py-0.5 bg-slate-100 rounded text-[9px] font-mono text-slate-500">
                            {event.entity_type}:{event.entity_id}
                        </span>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                        by {event.actor} • {formatTimestamp(event.created_at)}
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <span className="text-[9px] font-mono text-slate-400 truncate max-w-[80px]">
                        #{event.event_hash?.slice(0, 8)}...
                    </span>
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </div>
            </button>

            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="border-t border-slate-100 bg-slate-50"
                    >
                        <div className="px-3 py-2 space-y-2">
                            <div className="grid grid-cols-2 gap-2 text-[10px]">
                                <div>
                                    <span className="text-slate-500">Event Hash:</span>
                                    <code className="ml-1 font-mono text-slate-700">{event.event_hash}</code>
                                </div>
                                <div>
                                    <span className="text-slate-500">Previous Hash:</span>
                                    <code className="ml-1 font-mono text-slate-700">{event.prev_hash}</code>
                                </div>
                            </div>
                            {event.payload && (
                                <div className="text-[10px]">
                                    <span className="text-slate-500">Payload:</span>
                                    <pre className="mt-1 p-2 bg-white border border-slate-200 rounded text-[9px] font-mono overflow-x-auto">
                                        {JSON.stringify(event.payload, null, 2)}
                                    </pre>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default AuditTrailPanel;
