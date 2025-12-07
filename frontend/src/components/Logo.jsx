// src/Logo.jsx
import React from 'react';
import logo from './assets/logo.png';

export const AureonLogo = ({ className = '', zoom = false }) => {
  if (zoom) {
    return (
      <div className={`relative overflow-hidden rounded-lg ${className}`}>
        <img
          src={logo}
          alt="Aureon Logo"
          className="w-full h-full object-cover scale-150"
        />
      </div>
    );
  }

  return (
    <img
      src={logo}
      alt="Aureon Logo"
      className={`object-contain ${className}`}
    />
  );
};
