import React, { useState, useEffect } from "react";
import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import Features from "./components/Features";
import SearchSection from "./components/SearchSection";
import ResultsSection from "./components/ResultsSection";
import Contact from "./components/Contact";
import FloatingThemeToggle from "./components/FloatingThemeToggle";
import Footer from "./components/Footer";
import Privacy from "./components/Privacy";
import Terms from "./components/Terms";
import ToastContainer from "./components/ToastContainer";
import { useSearch } from "./hooks/useSearch";
import "./styles/globals.css";
import "./App.css";

function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [route, setRoute] = useState(() => window.location.pathname);

  useEffect(() => {
    const onPop = () => setRoute(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // Use custom hook for search functionality (no local storage)
  const {
    loading,
    loadingProgress,
    loadingStage,
    error,
    setError,
    handleSearch,
  } = useSearch();

  // Clear error state when query changes (no need to show toast here since SearchSection handles it)
  useEffect(() => {
    if (error) {
      setError(null);
    }
  }, [query, setError]);

  // Handle search with error handling
  const onSearch = async () => {
    try {
      const searchResults = await handleSearch(query);
      if (searchResults) {
        setResults(searchResults);
      }
    } catch (error) {
      // Error is already handled by the useSearch hook and stored in error state
      // No need to show alert since ErrorDisplay component will show the error
      console.error("Search error:", error);
    }
  };

  // Clear error when query changes
  useEffect(() => {
    if (error) {
      setError(null);
    }
  }, [query, setError]);

  const scrollToSelector = (selector, offset) => {
    const el = document.querySelector(selector);
    if (!el) return;
    const y = el.getBoundingClientRect().top + window.pageYOffset + offset;
    window.scrollTo({ top: y, behavior: "smooth" });
  };

  // Handle section changes from navbar - works from any route
  const handleSectionChange = (section) => {
    const goAndScroll = () => {
      if (section === "about") {
        scrollToSelector(".features-section", -60);
      } else if (section === "search") {
        scrollToSelector("#search-section", -100);
      } else if (section === "contact") {
        scrollToSelector("#contact-section", -80);
      }
    };

    // Always navigate to root first if not already there
    if (route !== "/") {
      window.history.pushState({}, "", "/");
      setRoute("/");
      // Wait for main sections to mount and then scroll
      setTimeout(goAndScroll, 100);
    } else {
      goAndScroll();
    }
  };

  // Simple client-side navigation for footer links
  const renderRoute = () => {
    if (route === "/privacy") return <Privacy />;
    if (route === "/terms") return <Terms />;

    return (
      <>
        <Hero onGetStarted={handleGetStarted} onWatchDemo={handleWatchDemo} />
        <Features />
        <section id="search-section">
          <SearchSection
            query={query}
            setQuery={setQuery}
            onSearch={onSearch}
            loading={loading}
            hasResults={!loading && results}
            loadingProgress={loadingProgress}
            loadingStage={loadingStage}
            error={error}
            onValidationError={setError}
          />
        </section>
        {!loading && results && <ResultsSection results={results} />}
        <section id="contact-section">
          <Contact />
        </section>
      </>
    );
  };

  // Hero button handlers
  const handleGetStarted = () => {
    const searchSection = document.querySelector("#search-section");
    if (searchSection) {
      const yOffset = -100;
      const y =
        searchSection.getBoundingClientRect().top +
        window.pageYOffset +
        yOffset;
      window.scrollTo({ top: y, behavior: "smooth" });
      setTimeout(() => {
        const searchInput = document.querySelector('input[type="text"]');
        if (searchInput) {
          searchInput.focus();
        }
      }, 100);
    }
  };

  const handleWatchDemo = () => {
    alert("Demo video coming soon! 🎥");
  };

  return (
    <div className="app-wrapper">
      <Navbar onSectionChange={handleSectionChange} />
      {renderRoute()}
      <Footer />
      <FloatingThemeToggle />
      <ToastContainer />
    </div>
  );
}

export default App;
