import { useCallback, useEffect, useState } from "react";
import Navbar from "./components/Navbar";
import Features from "./components/Features";
import SearchSection from "./components/SearchSection";
import ResultsSection from "./components/ResultsSection";
import Contact from "./components/Contact";
import FloatingThemeToggle from "./components/FloatingThemeToggle";
import Footer from "./components/Footer";
import Privacy from "./components/Privacy";
import Terms from "./components/Terms";
import { useSearch } from "./hooks/useSearch";
import { loadRecentSearches, rememberSearch, validateQuery } from "./utils/tools";
import "./styles/globals.css";
import "./App.css";

function App() {
  const [query, setQuery] = useState(
    () => new URLSearchParams(window.location.search).get("q") ?? ""
  );
  const [recentSearches, setRecentSearches] = useState(loadRecentSearches);
  const [route, setRoute] = useState(() => window.location.pathname);

  const {
    loading,
    loadingProgress,
    loadingStage,
    streamedTools,
    results,
    error,
    setError,
    handleSearch,
    cancel,
  } = useSearch();

  useEffect(() => {
    const onPop = () => setRoute(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const runSearch = useCallback(
    async (text: string) => {
      const url = new URL(window.location.href);
      url.searchParams.set("q", text.trim());
      window.history.replaceState({}, "", url);
      if (await handleSearch(text)) {
        setRecentSearches(rememberSearch(text));
      }
    },
    [handleSearch]
  );

  // Run the search from a shared link once when the page opens.
  useEffect(() => {
    const shared = new URLSearchParams(window.location.search).get("q");
    if (!shared || validateQuery(shared) !== null) return undefined;
    const timer = setTimeout(() => void runSearch(shared), 0);
    return () => clearTimeout(timer);
  }, [runSearch]);

  const scrollToSelector = (selector: string, offset: number) => {
    const el = document.querySelector(selector);
    if (!el) return;
    const y = el.getBoundingClientRect().top + window.scrollY + offset;
    window.scrollTo({ top: y, behavior: "smooth" });
  };

  const handleSectionChange = (section: string) => {
    const goAndScroll = () => {
      if (section === "about") {
        scrollToSelector(".features-section", -60);
      } else if (section === "search") {
        window.scrollTo({ top: 0, behavior: "smooth" });
      } else if (section === "contact") {
        scrollToSelector("#contact-section", -80);
      }
    };

    if (route !== "/") {
      window.history.pushState({}, "", "/");
      setRoute("/");
      setTimeout(goAndScroll, 100);
    } else {
      goAndScroll();
    }
  };

  const renderRoute = () => {
    if (route === "/privacy") return <Privacy />;
    if (route === "/terms") return <Terms />;

    return (
      <>
        <section id="search-section" className="search-first">
          <SearchSection
            query={query}
            setQuery={setQuery}
            onSearch={(text) => void runSearch(text)}
            onCancel={cancel}
            loading={loading}
            hasResults={results !== null || streamedTools.length > 0}
            loadingProgress={loadingProgress}
            loadingStage={loadingStage}
            error={error}
            onError={setError}
            recentSearches={recentSearches}
          />
        </section>
        <ResultsSection results={results} streamedTools={streamedTools} loading={loading} />
        <Features />
        <section id="contact-section">
          <Contact />
        </section>
      </>
    );
  };

  return (
    <div className="app-wrapper">
      <Navbar onSectionChange={handleSectionChange} />
      {renderRoute()}
      <Footer />
      <FloatingThemeToggle />
    </div>
  );
}

export default App;
