import React, { useState, useEffect } from "react";
import "./Navbar.css";

const navigation = [
  { name: "About", section: "about" },
  { name: "Search", section: "search" },
  { name: "Contact", section: "contact" },
];

const Navbar = ({ onSectionChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const [isDark, setIsDark] = useState(false);

  // Handle scroll detection
  useEffect(() => {
    const handleScroll = () => {
      const scrollTop = window.scrollY;
      setIsScrolled(scrollTop > 50);
    };

    window.addEventListener("scroll", handleScroll);
    handleScroll();

    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Detect theme changes
  useEffect(() => {
    const checkTheme = () => {
      const isDarkMode =
        document.documentElement.classList.contains("dark") ||
        document.body.classList.contains("dark");
      setIsDark(isDarkMode);
    };

    checkTheme();
    const observer = new MutationObserver(checkTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ["class"],
    });

    return () => observer.disconnect();
  }, []);

  const handleNavClick = (section) => {
    onSectionChange(section);
    setIsOpen(false);
  };

  const toggleMobileMenu = () => {
    setIsOpen(!isOpen);
  };

  return (
    <>
      <nav
        className={`navbar ${isScrolled ? "scrolled" : ""} ${
          isDark ? "dark" : "light"
        }`}
      >
        <div className="navbar-container">
          {/* Logo and Brand */}
          <div
            className="brand"
            onClick={() => {
              if (window.location.pathname !== "/") {
                window.history.pushState({}, "", "/");
                window.dispatchEvent(new PopStateEvent("popstate"));
                setTimeout(
                  () => window.scrollTo({ top: 0, behavior: "smooth" }),
                  50
                );
              } else {
                window.scrollTo({ top: 0, behavior: "smooth" });
              }
            }}
          >
            <span className="brand-text">Tool Scraper</span>
          </div>

          {/* Desktop Navigation */}
          <div className="desktop-nav">
            {navigation.map((item) => (
              <button
                key={item.name}
                onClick={() => handleNavClick(item.section)}
                className="nav-link"
              >
                {item.name}
              </button>
            ))}
          </div>

          {/* Mobile Menu Button */}
          <button
            className="mobile-menu-btn"
            onClick={toggleMobileMenu}
            aria-label="Toggle mobile menu"
          >
            <svg
              className="menu-icon"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d={isOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"}
              />
            </svg>
          </button>
        </div>
      </nav>

      {/* Mobile Menu Overlay */}
      {isOpen && (
        <div className="mobile-overlay" onClick={() => setIsOpen(false)} />
      )}

      {/* Mobile Menu */}
      <div
        className={`mobile-menu ${isOpen ? "open" : ""} ${
          isDark ? "dark" : "light"
        }`}
      >
        <div className="mobile-menu-content">
          {navigation.map((item) => (
            <button
              key={item.name}
              onClick={() => handleNavClick(item.section)}
              className="mobile-nav-link"
            >
              {item.name}
            </button>
          ))}
        </div>
      </div>
    </>
  );
};

export default Navbar;
