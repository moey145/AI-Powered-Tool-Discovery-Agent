import { useEffect, useState, type MouseEvent } from "react";
import { LuMenu, LuMoon, LuSun, LuX } from "react-icons/lu";
import { useTheme } from "../contexts/useTheme";
import "./Navbar.css";

const SECTIONS = [
  { name: "Search", section: "search" },
  { name: "How it works", section: "about" },
  { name: "Contact", section: "contact" },
];

const Navbar = ({ onSectionChange }: { onSectionChange: (section: string) => void }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const { isDarkMode, toggleTheme } = useTheme();

  useEffect(() => {
    const onScroll = () => setIsScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setIsOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen]);

  const go = (section: string) => {
    onSectionChange(section);
    setIsOpen(false);
  };

  const goHome = (e: MouseEvent) => {
    e.preventDefault();
    setIsOpen(false);
    if (window.location.pathname !== "/") {
      window.history.pushState({}, "", "/");
      window.dispatchEvent(new PopStateEvent("popstate"));
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const links = (
    <>
      {SECTIONS.map((item) => (
        <button key={item.section} className="nav-link" onClick={() => go(item.section)}>
          {item.name}
        </button>
      ))}
      <a className="nav-link" href="/guides/">
        Guides
      </a>
    </>
  );

  return (
    <header className={`navbar ${isScrolled || isOpen ? "scrolled" : ""}`}>
      <div className="navbar-inner container">
        <a href="/" className="brand" onClick={goHome}>
          <span className="brand-mark" aria-hidden="true" />
          Tool Scraper
        </a>

        <nav className="nav-links" aria-label="Main">
          {links}
        </nav>

        <div className="nav-actions">
          <button
            className="icon-button"
            onClick={toggleTheme}
            aria-label={`Switch to ${isDarkMode ? "light" : "dark"} mode`}
            title={`Switch to ${isDarkMode ? "light" : "dark"} mode`}
          >
            {isDarkMode ? <LuSun size={18} /> : <LuMoon size={18} />}
          </button>
          <button
            className="icon-button menu-button"
            onClick={() => setIsOpen((open) => !open)}
            aria-label={isOpen ? "Close menu" : "Open menu"}
            aria-expanded={isOpen}
          >
            {isOpen ? <LuX size={20} /> : <LuMenu size={20} />}
          </button>
        </div>
      </div>

      {isOpen && (
        <nav className="mobile-menu container" aria-label="Mobile">
          {links}
        </nav>
      )}
    </header>
  );
};

export default Navbar;
