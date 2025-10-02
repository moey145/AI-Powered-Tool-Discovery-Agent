import React from "react";
import "./Hero.css";

const Hero = ({ onGetStarted, onWatchDemo }) => {
  const scrollToFeatures = () => {
    const featuresSection = document.querySelector(".features-section");
    if (featuresSection) {
      const yOffset = -60;
      const y =
        featuresSection.getBoundingClientRect().top +
        window.pageYOffset +
        yOffset;
      window.scrollTo({ top: y, behavior: "smooth" });
    }
  };

  return (
    <section className="hero-section">
      {/* Background Grid Pattern */}
      <div className="hero-background-grid" />

      <div className="hero-container">
        <div className="hero-content">
          {/* Badge */}
          <div className="hero-badge">
            <span className="badge-icon">🔍</span>
            <span className="badge-text">
              AI-Powered Tool Discovery & Analysis
            </span>
          </div>

          {/* Main Heading */}
          <h1 className="hero-title">
            Find the Perfect
            <span className="hero-gradient-text"> Tools </span>
            for Your Projects
          </h1>

          {/* Description */}
          <p className="hero-description">
            Discover, analyze, and compare developer tools, frameworks, and
            technologies. Get comprehensive insights on pricing, features, and
            tech stacks instantly.
          </p>

          {/* Call to Action Buttons */}
          <div className="hero-cta-buttons">
            <button
              className="hero-btn hero-btn-primary"
              onClick={() => onGetStarted && onGetStarted()}
            >
              Try It Now
            </button>

            <button
              className="hero-btn hero-btn-secondary"
              onClick={scrollToFeatures}
            >
              Learn More
            </button>
          </div>
        </div>
      </div>

      {/* Scroll Down Arrow */}
      <button
        className="scroll-down-arrow"
        onClick={scrollToFeatures}
        aria-label="Scroll to features section"
      >
        <div className="arrow-container">
          <svg
            className="arrow-icon"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
        </div>
      </button>
    </section>
  );
};

export default Hero;
