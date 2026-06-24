"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

export default function PasswordInput({
  value,
  onChange,
  placeholder,
  autoComplete,
  className = "",
  required,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoComplete?: string;
  className?: string;
  required?: boolean;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        className={`${className} pr-9`}
      />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        aria-label={show ? "隱藏密碼" : "顯示密碼"}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}
