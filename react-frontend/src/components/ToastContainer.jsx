import React, { useState, useCallback } from "react";
import Toast from "./Toast";

const ToastContainer = () => {
  const [toasts, setToasts] = useState([]);

  // Add toast function - can be called from anywhere via context or props
  const addToast = useCallback((message, type = "error", duration = 5000) => {
    // Check if identical toast already exists (prevent duplicates)
    setToasts((prev) => {
      const exists = prev.some(
        (toast) => toast.message === message && toast.type === type
      );

      if (exists) {
        return prev; // Don't add duplicate
      }

      const id = Date.now() + Math.random();
      const newToast = { id, message, type, duration };

      // Auto-remove after duration
      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }

      return [...prev, newToast];
    });
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  // Expose addToast globally for easy access
  React.useEffect(() => {
    window.addToast = addToast;
    return () => {
      delete window.addToast;
    };
  }, [addToast]);

  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          duration={toast.duration}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </div>
  );
};

export default ToastContainer;
