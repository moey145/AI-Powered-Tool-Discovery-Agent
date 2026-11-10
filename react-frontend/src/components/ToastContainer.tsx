import { useCallback, useState, type ReactNode } from "react";
import Toast from "./Toast";
import { ToastContext, type AddToast, type ToastType } from "../contexts/useToast";

interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
  duration: number;
}

const ToastProvider = ({ children }: { children: ReactNode }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const addToast = useCallback<AddToast>((message, type = "error", duration = 5000) => {
    setToasts((prev) => {
      if (prev.some((toast) => toast.message === message && toast.type === type)) {
        return prev;
      }
      return [...prev, { id: Date.now() + Math.random(), message, type, duration }];
    });
  }, []);

  return (
    <ToastContext.Provider value={addToast}>
      {children}
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
    </ToastContext.Provider>
  );
};

export default ToastProvider;
