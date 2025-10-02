import React from "react";
import "./StaticPages.css";

const Privacy = () => {
  const backHome = (e) => {
    e.preventDefault();
    if (window.location.pathname !== "/") {
      window.history.pushState({}, "", "/");
      window.dispatchEvent(new PopStateEvent("popstate"));
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <main className="static-container">
      <a href="/" className="back-home" onClick={backHome}>
        ← Back to Home
      </a>
      <header className="static-header">
        <h1>Privacy Policy</h1>
      </header>
      <section className="static-section">
        <p>
          <strong>Last updated: September 17, 2025</strong>
        </p>

        <p>
          Tool Scraper ("we," "our," or "us") is committed to protecting your
          privacy. This Privacy Policy explains how we handle information when
          you use our AI-powered tool discovery and analysis service ("the
          Service").
        </p>

        <h2>2. Information We Do NOT Store</h2>
        <p>
          We do not store any user information or search data on our servers.
          Specifically:
        </p>
        <ul>
          <li>Personal identification information</li>
          <li>
            Contact form submissions (these may be stored by third-party
            services)
          </li>
        </ul>

        <h2>3. Data Processing Through Third-Party AI Services</h2>
        <p>
          To provide our services, we pass your data to third-party AI services
          for processing:
        </p>
        <ul>
          <li>
            <strong>OpenAI:</strong> For tool analysis and recommendations
          </li>
          <li>
            <strong>Google Custom Search API:</strong> For web search and
            content discovery
          </li>
          <li>
            <strong>BeautifulSoup:</strong> For gathering tool information
          </li>
        </ul>
        <p>
          <strong>Important:</strong> These third-party services may temporarily
          process your data according to their own privacy policies. Data
          processing occurs in real-time and is not stored by us.
        </p>

        <h2>4. What Data is Processed</h2>
        <p>When you use our Service, the following data may be processed:</p>
        <ul>
          <li>Tool discovery queries you submit</li>
          <li>Technology and framework names you search for</li>
          <li>Contact form submissions (name, email, message)</li>
        </ul>

        <h2>5. How We Use Information</h2>
        <p>Information is processed solely to:</p>
        <ul>
          <li>Provide tool discovery and analysis results</li>
          <li>Generate comprehensive tool recommendations</li>
          <li>Conduct web research and tool profiling</li>
          <li>Improve service functionality and performance</li>
          <li>Respond to contact form inquiries</li>
        </ul>

        <h2>6. Data Security</h2>
        <p>
          While we do not store your data, we implement security measures during
          processing:
        </p>
        <ul>
          <li>HTTPS encryption for all data transmission</li>
          <li>Secure connections to third-party AI services</li>
          <li>Regular security updates and monitoring</li>
          <li>Limited access to processing systems</li>
        </ul>

        <h2>7. Your Responsibilities</h2>
        <p>To protect your privacy, you should:</p>
        <ul>
          <li>
            Never submit confidential or sensitive information in search queries
          </li>
          <li>Only search for publicly available tool information</li>
          <li>Avoid including personal identification details in searches</li>
          <li>Use the Service only for legitimate research purposes</li>
        </ul>

        <h2>8. International Data Transfers</h2>
        <p>
          Your data may be processed by third-party AI services located outside
          Australia, including:
        </p>
        <ul>
          <li>United States (OpenAI, Google)</li>
          <li>Other countries where these services operate</li>
        </ul>
        <p>
          By using our Service, you consent to this international processing.
        </p>

        <h2>9. Cookies and Analytics</h2>
        <p>We may use:</p>
        <ul>
          <li>Essential cookies for website functionality</li>
          <li>Analytics tools to understand usage patterns</li>
          <li>Performance monitoring for service improvement</li>
        </ul>
        <p>
          No personal identification information is collected through these
          tools.
        </p>

        <h2>10. Third-Party Links</h2>
        <p>
          Our Service may contain links to third-party websites and tools. We
          are not responsible for the privacy practices of these external sites.
          Please review their privacy policies separately.
        </p>

        <h2>11. Children's Privacy</h2>
        <p>
          Our Service is not intended for children under 16. We do not knowingly
          collect personal information from children under 16 without parental
          consent.
        </p>

        <h2>12. Changes to Privacy Policy</h2>
        <p>
          We may update this Privacy Policy periodically. Changes will be posted
          on this page with an updated date. Your continued use of the Service
          constitutes acceptance of any changes.
        </p>

        <h2>13. Australian Privacy Law Compliance</h2>
        <p>
          This Privacy Policy is designed to comply with the Australian Privacy
          Act 1988 and the Australian Privacy Principles (APPs). As we do not
          store personal information, many traditional privacy obligations do
          not apply to our Service.
        </p>

        <h2>14. Contact Us</h2>
        <p>
          If you have any questions about this Privacy Policy or our privacy
          practices, please contact us at{" "}
          <a href="mailto:mohamad.eldhaibi@gmail.com" className="static-link">
            mohamad.eldhaibi@gmail.com
          </a>
        </p>

        <p>
          <strong>Effective Date:</strong> September 17, 2025
        </p>
      </section>
    </main>
  );
};

export default Privacy;
