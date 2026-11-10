import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import ToastProvider from "./components/ToastContainer";
import { ThemeProvider } from "./contexts/ThemeContext";
import "./styles/globals.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </ThemeProvider>
  </StrictMode>
);
