import React, { useEffect, useState } from "react";
import "./Toast.css";

const Toast = ({ message, type = "error", duration = 5000, onClose }) => {
  const [isVisible, setIsVisible] = useState(true);
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        handleClose();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [duration]);

  const handleClose = () => {
    setIsExiting(true);
    setTimeout(() => {
      setIsVisible(false);
      if (onClose) {
        onClose();
      }
    }, 300); // Match CSS transition duration
  };

  if (!isVisible) return null;

  const getIcon = () => {
    switch (type) {
      case "success":
        return "✅";
      case "warning":
        return "⚠️";
      case "info":
        return "ℹ️";
      case "error":
      default:
        return "❌";
    }
  };

  const getTitle = () => {
    switch (type) {
      case "success":
        return "Success";
      case "warning":
        return "Warning";
      case "info":
        return "Info";
      case "error":
      default:
        return "Error";
    }
  };

  return (
    <div className={`toast ${type} ${isExiting ? "exiting" : ""}`}>
      <div className="toast-content">
        <div className="toast-icon">{getIcon()}</div>
        <div className="toast-body">
          <div className="toast-title">{getTitle()}</div>
          <div className="toast-message">{message}</div>
        </div>
        <button
          className="toast-close"
          onClick={handleClose}
          aria-label="Close notification"
        >
          ×
        </button>
      </div>
      <div className="toast-progress">
        <div
          className="toast-progress-bar"
          style={{
            animationDuration: `${duration}ms`,
            animationPlayState: isExiting ? "paused" : "running",
          }}
        />
      </div>
    </div>
  );
};

export default Toast;
