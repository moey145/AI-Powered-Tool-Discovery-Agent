import { FaMagnifyingGlass, FaChartColumn } from "react-icons/fa6";
import { BsLightningFill } from "react-icons/bs";
import "./Features.css";

const features = [
  {
    icon: <FaMagnifyingGlass className="feature-icon" />,
    title: "Smart Tool Discovery",
    description:
      "Our AI-powered scraper finds the best tools for your specific needs. Just describe what you're looking for and get comprehensive results instantly.",
  },
  {
    icon: <FaChartColumn className="feature-icon" />,
    title: "Comprehensive Analysis",
    description:
      "See pricing, licensing, GitHub activity, and the sources behind every result. Compare tools side by side to make informed decisions.",
  },
  {
    icon: <BsLightningFill className="feature-icon" />,
    title: "Real-time Data",
    description:
      "Each search reads live web pages, so results reflect what tools say about their features and pricing today, with results appearing as they finish.",
  },
];

const Features = () => (
  <section id="features" className="features-section">
    <div className="features-container">
      <div className="features-header">
        <h2 className="features-title">
          Why Choose{" "}
          <span className="features-gradient-text">Tool Scraper</span>
        </h2>
        <p className="features-description">
          Discover the powerful features that make tool discovery effortless and
          comprehensive
        </p>
      </div>
      <div className="features-grid">
        {features.map((feature, index) => (
          <div key={index} className="feature-card">
            <div className="feature-icon-wrapper">
              <span className="feature-icon">{feature.icon}</span>
            </div>
            <div className="feature-content">
              <h3 className="feature-title">{feature.title}</h3>
              <p className="feature-description">{feature.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  </section>
);

export default Features;
