import React from "react";
import "./Footer.css";

const Footer = () => {
  const currentYear = new Date().getFullYear();

  const navigate = (path, e) => {
    e.preventDefault();
    if (window.location.pathname !== path) {
      window.history.pushState({}, "", path);
      window.dispatchEvent(new PopStateEvent("popstate"));
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <footer className="app-footer">
      <div className="footer-container">
        <div className="footer-bottom">
          <span className="footer-copy">
            © {currentYear} Tool Scraper — All Rights Reserved
          </span>
          <nav className="footer-links">
            <a
              href="/privacy"
              className="footer-link"
              onClick={(e) => navigate("/privacy", e)}
            >
              Privacy Policy
            </a>
            <span className="footer-sep">•</span>
            <a
              href="/terms"
              className="footer-link"
              onClick={(e) => navigate("/terms", e)}
            >
              Terms of Service
            </a>
          </nav>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
