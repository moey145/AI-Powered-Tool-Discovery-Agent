import { createContext, useContext } from "react";

export type ToastType = "success" | "warning" | "info" | "error";
export type AddToast = (message: string, type?: ToastType, duration?: number) => void;

export const ToastContext = createContext<AddToast | null>(null);

export const useToast = (): AddToast => {
  const addToast = useContext(ToastContext);
  if (!addToast) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return addToast;
};
