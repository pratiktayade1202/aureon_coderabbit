// src/components/SettingsView.jsx
// Thin wrapper that mounts the terminal-style settings console

import React from "react";
import SettingsLayout from "./settings/SettingsLayout";

const SettingsView = ({ resetDatabase }) => {
  return <SettingsLayout resetDatabase={resetDatabase} />;
};

export default SettingsView;
