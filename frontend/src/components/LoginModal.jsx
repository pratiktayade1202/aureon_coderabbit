// src/components/LoginModal.jsx
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Lock, Building2, AlertTriangle } from "lucide-react";
import { SignIn } from "@clerk/clerk-react";

/**
 * LoginModal
 *
 * Institutional login gate:
 * - No playful gradients, more like an internal tool access screen
 */
const LoginModal = ({ isOpen, onClose }) => {
  const [showError, setShowError] = useState(false);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[200] flex items-center justify-center px-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.75 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-slate-900/80 backdrop-blur-sm"
          onClick={onClose}
        />

        {/* Panel */}
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 8 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="relative w-full max-w-md bg-white border border-slate-300 rounded-lg shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="px-5 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 flex items-center justify-center rounded-md bg-slate-900 text-white">
                <Lock size={16} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-slate-900 tracking-tight">
                  Secure Access
                </h2>
                <p className="text-[11px] text-slate-600 flex items-center gap-1.5">
                  <Building2 size={11} className="text-slate-500" />
                  Aureon Enterprise Workspace
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md text-slate-500 hover:bg-slate-100 transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* Body */}
          <div className="px-5 py-5 bg-slate-50/80">
            <p className="text-xs text-slate-600 mb-4">
              Use your institutional account to access the reconciliation workspace.  
              All actions are recorded in the audit trail.
            </p>

            {showError && (
              <div className="mb-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2">
                <AlertTriangle size={14} className="mt-0.5 text-red-600" />
                <p className="text-[11px] text-red-700">
                  Invalid credentials. Access is restricted to provisioned tenant users.
                </p>
              </div>
            )}

            <div className="rounded-md border border-slate-200 bg-white px-4 py-4">
              {/* Clerk Hosted Component */}
              <SignIn
                appearance={{
                  elements: {
                    formButtonPrimary:
                      "bg-slate-900 text-white hover:bg-slate-800 text-xs font-semibold rounded-md",
                    footer: "hidden",
                  },
                }}
                redirectUrl="/app"
                afterSignInUrl="/app"
                signUpUrl="/sign-up"
              />
            </div>

            <p className="mt-3 text-[10px] text-slate-500">
              By signing in you acknowledge that Aureon is a monitored environment.  
              Sessions may be reviewed for risk and compliance.
            </p>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default LoginModal;
