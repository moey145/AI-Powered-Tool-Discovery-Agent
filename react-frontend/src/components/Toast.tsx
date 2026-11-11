import { useEffect, useEffectEvent, useState } from "react";
import type { IconType } from "react-icons";
import { LuCircleCheck, LuCircleX, LuInfo, LuTriangleAlert, LuX } from "react-icons/lu";
import type { ToastType } from "../contexts/useToast";
import "./Toast.css";

const ICONS: Record<ToastType, IconType> = {
  success: LuCircleCheck,
  warning: LuTriangleAlert,
  info: LuInfo,
  error: LuCircleX,
};

interface ToastProps {
  message: string;
  type?: ToastType;
  duration?: number;
  onClose?: () => void;
}

const Toast = ({ message, type = "error", duration = 5000, onClose }: ToastProps) => {
  const [isExiting, setIsExiting] = useState(false);
  const Icon = ICONS[type];

  const handleClose = () => {
    setIsExiting(true);
    setTimeout(() => onClose?.(), 180); // Matches the exit animation.
  };

  const onTimeout = useEffectEvent(handleClose);

  useEffect(() => {
    if (duration <= 0) return undefined;
    const timer = setTimeout(onTimeout, duration);
    return () => clearTimeout(timer);
  }, [duration]);

  return (
    <div
      className={`toast toast-${type} ${isExiting ? "exiting" : ""}`}
      role={type === "error" || type === "warning" ? "alert" : "status"}
    >
      <Icon className="toast-icon" size={18} aria-hidden="true" />
      <p className="toast-message">{message}</p>
      <button className="toast-close" onClick={handleClose} aria-label="Dismiss notification">
        <LuX size={16} />
      </button>
    </div>
  );
};

export default Toast;
