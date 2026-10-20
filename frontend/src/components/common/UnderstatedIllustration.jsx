import React from 'react';

export const UnderstatedIllustration = ({ className = 'w-full h-auto' }) => {
  return (
    <svg
      viewBox="0 0 480 360"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="QA Workspace verification illustration"
    >
      <defs>
        <linearGradient id="planeGrad" x1="0" y1="0" x2="480" y2="360" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4F46E5" stopOpacity="0.08" />
          <stop stopColor="#0F766E" stopOpacity="0.04" />
        </linearGradient>
        <linearGradient id="cardGrad1" x1="120" y1="80" x2="360" y2="280" gradientUnits="userSpaceOnUse">
          <stop stopColor="#FFFFFF" stopOpacity="0.9" />
          <stop stopColor="#F8FAFC" stopOpacity="0.8" />
        </linearGradient>
      </defs>

      {/* Subtle background ambient mesh */}
      <rect width="480" height="360" rx="16" fill="url(#planeGrad)" />
      
      {/* Grid lines simulating a testing workspace canvas */}
      <path d="M60 40H420M60 100H420M60 160H420M60 220H420M60 280H420M60 320H420" stroke="#E2E8F0" strokeWidth="1" strokeDasharray="3 3" />
      <path d="M100 30V330M180 30V330M260 30V330M340 30V330M400 30V330" stroke="#E2E8F0" strokeWidth="1" strokeDasharray="3 3" />

      {/* Main workspace test card */}
      <g filter="drop-shadow(0px 8px 16px rgba(15, 23, 42, 0.06))">
        <rect x="90" y="70" width="300" height="190" rx="12" fill="#FFFFFF" stroke="#CBD5E1" strokeWidth="1.5" />
        {/* Card Header */}
        <rect x="90" y="70" width="300" height="40" rx="12" fill="#F1F5F9" />
        <path d="M90 110H390" stroke="#E2E8F0" strokeWidth="1" />
        <circle cx="114" cy="90" r="4" fill="#94A3B8" />
        <circle cx="128" cy="90" r="4" fill="#CBD5E1" />
        <circle cx="142" cy="90" r="4" fill="#E2E8F0" />
        <rect x="165" y="84" width="90" height="12" rx="4" fill="#CBD5E1" />
        
        {/* Verification Check rows */}
        {/* Row 1 */}
        <rect x="114" y="128" width="16" height="16" rx="4" fill="#4F46E5" fillOpacity="0.1" stroke="#4F46E5" strokeWidth="1.5" />
        <path d="M118 136L122 140L126 132" stroke="#4F46E5" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <rect x="140" y="131" width="120" height="10" rx="3" fill="#334155" />
        <rect x="310" y="128" width="56" height="16" rx="8" fill="#F0FDF4" stroke="#86EFAC" strokeWidth="1" />
        <rect x="322" y="133" width="32" height="6" rx="3" fill="#16A34A" />

        {/* Row 2 */}
        <rect x="114" y="160" width="16" height="16" rx="4" fill="#0F766E" fillOpacity="0.1" stroke="#0F766E" strokeWidth="1.5" />
        <path d="M118 168L122 172L126 164" stroke="#0F766E" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <rect x="140" y="163" width="150" height="10" rx="3" fill="#64748B" />
        <rect x="310" y="160" width="56" height="16" rx="8" fill="#F0FDFA" stroke="#99F6E4" strokeWidth="1" />
        <rect x="322" y="165" width="32" height="6" rx="3" fill="#0F766E" />

        {/* Row 3 */}
        <rect x="114" y="192" width="16" height="16" rx="4" fill="#EEF2FF" stroke="#A5B4FC" strokeWidth="1.5" />
        <path d="M118 200L122 204L126 196" stroke="#4F46E5" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <rect x="140" y="195" width="100" height="10" rx="3" fill="#94A3B8" />
        <rect x="310" y="192" width="56" height="16" rx="8" fill="#F8FAFC" stroke="#E2E8F0" strokeWidth="1" />
        <rect x="322" y="197" width="32" height="6" rx="3" fill="#64748B" />

        {/* Card Footer status indicator */}
        <path d="M90 226H390" stroke="#F1F5F9" strokeWidth="1" />
        <circle cx="114" cy="242" r="5" fill="#0F766E" />
        <rect x="126" y="238" width="75" height="8" rx="2" fill="#64748B" />
        <rect x="330" y="236" width="36" height="12" rx="3" fill="#E2E8F0" />
      </g>

      {/* Floating secondary badge card */}
      <g filter="drop-shadow(0px 6px 12px rgba(15, 23, 42, 0.08))">
        <rect x="290" y="190" width="140" height="95" rx="10" fill="#FFFFFF" stroke="#CBD5E1" strokeWidth="1.2" />
        <rect x="306" y="206" width="24" height="24" rx="6" fill="#EEF2FF" />
        <path d="M314 218L317 221L322 215" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <rect x="338" y="210" width="60" height="8" rx="2" fill="#0F172A" />
        <rect x="338" y="222" width="40" height="6" rx="2" fill="#94A3B8" />
        <path d="M306 244H414" stroke="#F1F5F9" strokeWidth="1" />
        <rect x="306" y="254" width="70" height="6" rx="2" fill="#CBD5E1" />
        <rect x="306" y="265" width="90" height="6" rx="2" fill="#E2E8F0" />
      </g>
    </svg>
  );
};
