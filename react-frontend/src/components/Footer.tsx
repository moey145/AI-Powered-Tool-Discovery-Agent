import type { MouseEvent } from "react";
import "./Footer.css";

const Footer = () => {
  const currentYear = new Date().getFullYear();

  const navigate = (path: string, e: MouseEvent) => {
    e.preventDefault();
    if (window.location.pathname !== path) {
      window.history.pushState({}, "", path);
      window.dispatchEvent(new PopStateEvent("popstate"));
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <footer className="footer">
      <div className="footer-inner container">
        <span className="footer-brand">
          <span className="brand-mark" aria-hidden="true" />© {currentYear} Tool Scraper
        </span>
        <nav className="footer-links" aria-label="Footer">
          <a href="/guides/">Tool guides</a>
          <a href="/privacy" onClick={(e) => navigate("/privacy", e)}>
            Privacy
          </a>
          <a href="/terms" onClick={(e) => navigate("/terms", e)}>
            Terms
          </a>
        </nav>
      </div>
    </footer>
  );
};

export default Footer;
