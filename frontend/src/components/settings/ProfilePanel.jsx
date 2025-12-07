import React from "react";
import { useUser } from "@clerk/clerk-react";

const ProfilePanel = ({ onLogout }) => {
  const { user } = useUser();

  return (
    <div>
      <h2 className="text-lg font-semibold text-ink-strong mb-4">Profile</h2>

      <div className="flex items-center gap-4 mb-6">
        <img
          src={user?.imageUrl}
          alt=""
          className="w-14 h-14 rounded-full border border-aureon-border"
        />
        <div>
          <p className="text-sm font-medium text-ink-strong">{user?.fullName}</p>
          <p className="text-xs text-ink-muted">{user?.primaryEmailAddress?.emailAddress}</p>
        </div>
      </div>

      <button
        onClick={onLogout}
        className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700"
      >
        Logout
      </button>
    </div>
  );
};

export default ProfilePanel;
