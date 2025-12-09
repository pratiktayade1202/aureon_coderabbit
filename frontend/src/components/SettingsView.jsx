// src/components/SettingsView.jsx
// Thin wrapper that mounts the terminal-style settings console

import React from "react";
import SettingsLayout from "./settings/SettingsLayout";

const SettingsView = ({ resetDatabase }) => {
  // `resetDatabase` is currently handled via backend tooling / danger zone.
  // We keep the prop for compatibility but delegate UI to the new layout.
  return <SettingsLayout />;
};

export default SettingsView;
